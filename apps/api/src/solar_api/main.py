from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Annotated, Any

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from solar_store.repository import Repository


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql://solar:change-me-locally@127.0.0.1:5432/solar_monitor"
    api_auth_token: str = ""
    cors_origins: str = "*"
    site_timezone: str = "America/Los_Angeles"


settings = ApiSettings()
app = FastAPI(title="Solar Monitor API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise HTTPException(status_code=503, detail="database pool not ready")
    return _pool


async def get_repo(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> Repository:
    return Repository(pool)


def require_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = settings.api_auth_token.strip()
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != token:
        raise HTTPException(status_code=403, detail="invalid token")


@app.on_event("startup")
async def startup() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)


@app.on_event("shutdown")
async def shutdown() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@app.get("/health")
async def health(repo: Annotated[Repository, Depends(get_repo)]) -> dict[str, Any]:
    data = await repo.health()
    data["service"] = "solar-api"
    data["status"] = "ok" if data.get("database_ok") else "degraded"
    return data


@app.get("/ready")
async def ready(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> dict[str, str]:
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}


@app.get("/v1/current", dependencies=[Depends(require_auth)])
async def current(repo: Annotated[Repository, Depends(get_repo)]) -> dict[str, Any]:
    overview = await repo.current_overview()
    # JSON-serialize datetimes
    def conv(obj: Any) -> Any:
        if isinstance(obj, list):
            return [conv(x) for x in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return conv(overview)


@app.get("/v1/devices", dependencies=[Depends(require_auth)])
async def devices(repo: Annotated[Repository, Depends(get_repo)]) -> dict[str, Any]:
    rows = await repo.devices()

    def conv(obj: Any) -> Any:
        if isinstance(obj, list):
            return [conv(x) for x in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return {"devices": conv(rows)}


class DeviceLayoutUpdate(BaseModel):
    grid_row: int | None = Field(default=None, ge=0, le=50)
    grid_col: int | None = Field(default=None, ge=0, le=50)
    name: str | None = Field(default=None, max_length=80)


@app.patch("/v1/devices/{device_id}/layout", dependencies=[Depends(require_auth)])
async def patch_device_layout(
    device_id: str,
    body: DeviceLayoutUpdate,
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict[str, Any]:
    if body.grid_row is None and body.grid_col is None and body.name is None:
        raise HTTPException(status_code=400, detail="no layout fields provided")
    row = await repo.update_device_layout(
        device_id,
        grid_row=body.grid_row,
        grid_col=body.grid_col,
        name=body.name,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="inverter not found")

    def conv(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return {"device": conv(row)}


@app.get("/v1/day-summary", dependencies=[Depends(require_auth)])
async def day_summary(
    repo: Annotated[Repository, Depends(get_repo)],
) -> dict[str, Any]:
    """Calendar-day production and grid net in the configured site timezone."""
    return await repo.day_energy_summary(
        timezone_name=settings.site_timezone
    )

@app.get("/v1/production-history", dependencies=[Depends(require_auth)])
async def production_history(
    repo: Annotated[Repository, Depends(get_repo)],
    range: str = Query("week", pattern="^(day|week|month|year|all)$"),
) -> dict[str, Any]:
    """
    Calendar-based solar production history.

    day   = today's total
    week  = last 7 calendar days
    month = current calendar month, daily totals
    year  = current calendar year, monthly totals
    all   = collector history by year + actual lifetime total
    """

    zone = ZoneInfo(settings.site_timezone)
    today = datetime.now(zone).date()

    if range == "day":
        start_date: date | None = today
        end_date = today

    elif range == "week":
        start_date = today - timedelta(days=6)
        end_date = today

    elif range == "month":
        start_date = today.replace(day=1)
        end_date = today

    elif range == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today

    else:  # all
        start_date = None
        end_date = today

    daily_points = await repo.production_energy_by_day(
        start_date=start_date,
        end_date=end_date,
        timezone_name=settings.site_timezone,
    )

    total_kwh = sum(
        float(point["generated_kwh"])
        for point in daily_points
        if point["generated_kwh"] is not None
    )

    lifetime_kwh = None

    # Day / week / month return daily values.
    if range in ("day", "week", "month"):
        points = daily_points
        bucket = "day"

    # Year returns one point per month.
    elif range == "year":
        buckets: dict[str, float] = {}

        for point in daily_points:
            if point["generated_kwh"] is None:
                continue

            month = point["date"][:7]

            buckets[month] = (
                buckets.get(month, 0.0)
                + float(point["generated_kwh"])
            )

        points = [
            {
                "date": month,
                "generated_kwh": round(value, 3),
            }
            for month, value in sorted(buckets.items())
        ]

        bucket = "month"

    # All returns collector history grouped by year,
    # plus the actual lifetime cumulative total from the PVS.
    else:
        lifetime_kwh = await repo.lifetime_pv_energy()

        buckets: dict[str, float] = {}

        for point in daily_points:
            if point["generated_kwh"] is None:
                continue

            year = point["date"][:4]

            buckets[year] = (
                buckets.get(year, 0.0)
                + float(point["generated_kwh"])
            )

        points = [
            {
                "date": year,
                "generated_kwh": round(value, 3),
            }
            for year, value in sorted(buckets.items())
        ]

        bucket = "year"

    return {
        "range": range,
        "timezone": settings.site_timezone,
        "bucket": bucket,
        "total_kwh": round(total_kwh, 3),
        "lifetime_kwh": (
            round(lifetime_kwh, 3)
            if lifetime_kwh is not None
            else None
        ),
        "point_count": len(points),
        "points": points,
    }

@app.get("/v1/inverter-summary", dependencies=[Depends(require_auth)])
async def inverter_summary(
    repo: Annotated[Repository, Depends(get_repo)],
    range: str = Query("week", pattern="^(day|week|month|year|all)$"),
) -> dict[str, Any]:
    """Average generated power for each inverter over a calendar range."""
    zone = ZoneInfo(settings.site_timezone)
    today = datetime.now(zone).date()

    if range == "day":
        start_date: date | None = today
    elif range == "week":
        start_date = today - timedelta(days=6)
    elif range == "month":
        start_date = today.replace(day=1)
    elif range == "year":
        start_date = today.replace(month=1, day=1)
    else:
        start_date = None

    start = (
        datetime.combine(start_date, datetime.min.time(), tzinfo=zone).astimezone(timezone.utc)
        if start_date is not None
        else None
    )
    end = datetime.now(timezone.utc)
    data = await repo.inverter_range_summary(start=start, end=end)
    return {
        "range": range,
        "timezone": settings.site_timezone,
        "unit": "W",
        "start": data["start"],
        "end": data["end"],
        "values_w": {
            path: round(value * 1000, 1) if value is not None else None
            for path, value in data["values_kw"].items()
        },
        "max_w": round(data["max_kw"] * 1000, 1),
    }

@app.get("/v1/playback", dependencies=[Depends(require_auth)])
async def playback(
    repo: Annotated[Repository, Depends(get_repo)],
    hours: int = Query(24, ge=1, le=24 * 7),
) -> dict[str, Any]:
    """Inverter power frames for heatmap time-lapse scrubbing."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    data = await repo.inverter_playback(start=start, end=end)

    def conv(obj: Any) -> Any:
        if isinstance(obj, list):
            return [conv(x) for x in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return conv(data)


@app.get("/v1/history", dependencies=[Depends(require_auth)])
async def history(
    repo: Annotated[Repository, Depends(get_repo)],
    metric: str = Query(..., min_length=1, max_length=64),
    device_type: str | None = Query(None),
    pvs_path_id: str | None = Query(None),
    hours: int = Query(24, ge=1, le=24 * 90),
    limit: int = Query(5000, ge=1, le=20000),
) -> dict[str, Any]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    rows = await repo.history(
        metric=metric,
        device_type=device_type,
        pvs_path_id=pvs_path_id,
        start=start,
        end=end,
        limit=limit,
    )

    def conv(obj: Any) -> Any:
        if isinstance(obj, list):
            return [conv(x) for x in obj]
        if isinstance(obj, dict):
            return {k: conv(v) for k, v in obj.items()}
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return {
        "metric": metric,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": len(rows),
        "points": conv(rows),
    }


@app.get("/v1/export.csv", dependencies=[Depends(require_auth)])
async def export_csv(
    repo: Annotated[Repository, Depends(get_repo)],
    metric: str = Query("pv_power_kw"),
    device_type: str | None = Query("site"),
    pvs_path_id: str | None = Query("livedata"),
    hours: int = Query(24, ge=1, le=24 * 365),
) -> Response:
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    rows = await repo.history(
        metric=metric,
        device_type=device_type,
        pvs_path_id=pvs_path_id,
        start=start,
        end=end,
        limit=20000,
    )
    lines = ["time,device_type,pvs_path_id,metric,value,unit,quality,source"]
    for r in rows:
        lines.append(
            ",".join(
                [
                    r["time"].isoformat(),
                    str(r["device_type"]),
                    str(r["pvs_path_id"]),
                    metric,
                    str(r["value"]),
                    str(r["unit"]),
                    str(r["quality"]),
                    str(r["source"]),
                ]
            )
        )
    body = "\n".join(lines) + "\n"
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=solar-export.csv"},
    )
