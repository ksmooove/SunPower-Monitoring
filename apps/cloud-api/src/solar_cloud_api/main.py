"""Cloud read replica API: ingest from home, serve mobile clients."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any
import json

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql://solar:change-me@127.0.0.1:5432/solar_monitor_cloud"
    api_auth_token: str = ""
    cloud_sync_token: str = ""
    cors_origins: str = "*"


settings = Settings()
app = FastAPI(title="Solar Monitor Cloud API", version="0.1.0")
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


def _payload_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        return dict(json.loads(raw))
    if isinstance(raw, (bytes, bytearray)):
        return dict(json.loads(raw.decode("utf-8")))
    return dict(raw)


def require_phone_auth(authorization: Annotated[str | None, Header()] = None) -> None:
    token = settings.api_auth_token.strip()
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    if authorization.removeprefix("Bearer ").strip() != token:
        raise HTTPException(status_code=403, detail="invalid token")


def require_sync_auth(
    authorization: Annotated[str | None, Header()] = None,
    x_sync_token: Annotated[str | None, Header()] = None,
) -> None:
    token = settings.cloud_sync_token.strip()
    if not token:
        raise HTTPException(status_code=503, detail="CLOUD_SYNC_TOKEN not configured")
    provided = None
    if x_sync_token:
        provided = x_sync_token.strip()
    elif authorization and authorization.startswith("Bearer "):
        provided = authorization.removeprefix("Bearer ").strip()
    if not provided or provided != token:
        raise HTTPException(status_code=403, detail="invalid sync token")


@app.on_event("startup")
async def startup() -> None:
    global _pool
    _pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        # Plain tables — do not require Timescale for API boot.
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cloud_snapshots (
                    key TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cloud_history_points (
                    time TIMESTAMPTZ NOT NULL,
                    metric TEXT NOT NULL,
                    value DOUBLE PRECISION NOT NULL,
                    unit TEXT,
                    PRIMARY KEY (metric, time)
                );
                """
            )
        except Exception:
            # e.g. Timescale extension/library mismatch on the Postgres image —
            # surface a clear log and re-raise so the operator fixes the DB image.
            import logging

            logging.getLogger("solar_cloud_api").exception(
                "cloud schema init failed — check Timescale image matches the data volume"
            )
            raise
        try:
            await conn.execute(
                """
                SELECT create_hypertable(
                    'cloud_history_points', 'time',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
                """
            )
        except Exception:
            pass


@app.on_event("shutdown")
async def shutdown() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@app.get("/health")
async def health(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> dict[str, Any]:
    async with pool.acquire() as conn:
        ok = await conn.fetchval("SELECT 1")
        row = await conn.fetchrow(
            "SELECT payload, updated_at FROM cloud_snapshots WHERE key = 'health'"
        )
        current_at = await conn.fetchval(
            "SELECT updated_at FROM cloud_snapshots WHERE key = 'current'"
        )
    base: dict[str, Any] = {
        "service": "solar-cloud-api",
        "status": "ok" if ok == 1 else "degraded",
        "database_ok": ok == 1,
        "current_synced_at": current_at.isoformat() if current_at else None,
    }
    if row:
        base.update(_payload_dict(row["payload"]))
        base["snapshot_updated_at"] = row["updated_at"].isoformat()
    return base


@app.get("/ready")
async def ready(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> dict[str, str]:
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
    return {"status": "ready"}


@app.get("/v1/current", dependencies=[Depends(require_phone_auth)])
async def current(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payload, updated_at FROM cloud_snapshots WHERE key = 'current'"
        )
    if not row:
        raise HTTPException(status_code=404, detail="no current snapshot synced yet")
    payload = _payload_dict(row["payload"])
    payload["_cloud_synced_at"] = row["updated_at"].isoformat()
    return payload


@app.get("/v1/day-summary", dependencies=[Depends(require_phone_auth)])
async def day_summary(pool: Annotated[asyncpg.Pool, Depends(get_pool)]) -> dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payload, updated_at FROM cloud_snapshots WHERE key = 'day_summary'"
        )
    if not row:
        raise HTTPException(status_code=404, detail="no day summary synced yet")
    payload = _payload_dict(row["payload"])
    payload["_cloud_synced_at"] = row["updated_at"].isoformat()
    return payload


@app.get("/v1/history", dependencies=[Depends(require_phone_auth)])
async def history(
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
    metric: str = "pv_power_kw",
    hours: int = 24,
) -> dict[str, Any]:
    if hours < 1 or hours > 24 * 90:
        raise HTTPException(status_code=400, detail="hours out of range")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT time, value, unit
            FROM cloud_history_points
            WHERE metric = $1
              AND time >= now() - make_interval(hours => $2::int)
            ORDER BY time ASC
            """,
            metric,
            hours,
        )
    return {
        "metric": metric,
        "hours": hours,
        "count": len(rows),
        "points": [
            {
                "time": r["time"].isoformat(),
                "value": r["value"],
                "unit": r["unit"] or "kW",
            }
            for r in rows
        ],
    }


class HistoryPoint(BaseModel):
    time: datetime
    metric: str
    value: float
    unit: str | None = "kW"


class IngestPayload(BaseModel):
    health: dict[str, Any] | None = None
    current: dict[str, Any] | None = None
    day_summary: dict[str, Any] | None = None
    history_points: list[HistoryPoint] = Field(default_factory=list)


@app.post("/v1/ingest", dependencies=[Depends(require_sync_auth)])
async def ingest(
    body: IngestPayload,
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        async with conn.transaction():
            if body.health is not None:
                await conn.execute(
                    """
                    INSERT INTO cloud_snapshots (key, payload, updated_at)
                    VALUES ('health', $1::jsonb, $2)
                    ON CONFLICT (key) DO UPDATE
                      SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                    """,
                    json.dumps(body.health),
                    now,
                )
            if body.current is not None:
                await conn.execute(
                    """
                    INSERT INTO cloud_snapshots (key, payload, updated_at)
                    VALUES ('current', $1::jsonb, $2)
                    ON CONFLICT (key) DO UPDATE
                      SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                    """,
                    json.dumps(body.current),
                    now,
                )
            if body.day_summary is not None:
                await conn.execute(
                    """
                    INSERT INTO cloud_snapshots (key, payload, updated_at)
                    VALUES ('day_summary', $1::jsonb, $2)
                    ON CONFLICT (key) DO UPDATE
                      SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                    """,
                    json.dumps(body.day_summary),
                    now,
                )
            if body.history_points:
                await conn.executemany(
                    """
                    INSERT INTO cloud_history_points (time, metric, value, unit)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (metric, time) DO UPDATE
                      SET value = EXCLUDED.value, unit = EXCLUDED.unit
                    """,
                    [
                        (p.time, p.metric, p.value, p.unit)
                        for p in body.history_points
                    ],
                )
    return {
        "status": "ok",
        "ingested_at": now.isoformat(),
        "history_points": len(body.history_points),
    }
