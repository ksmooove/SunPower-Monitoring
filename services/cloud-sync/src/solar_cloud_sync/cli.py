from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from solar_store.repository import Repository

log = logging.getLogger("solar-cloud-sync")


class SyncSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    database_url: str = "postgresql://solar:change-me-locally@127.0.0.1:5432/solar_monitor"
    cloud_sync_url: str = "https://solar.blackmagicsoftware.net"
    cloud_sync_token: str = ""
    cloud_sync_interval_seconds: int = 300
    cloud_sync_history_hours: int = 48
    log_level: str = "INFO"


def _jsonable(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return obj


async def build_payload(repo: Repository, history_hours: int) -> dict[str, Any]:
    health = _jsonable(await repo.health())
    current = _jsonable(await repo.current_overview())
    day = _jsonable(await repo.day_energy_summary(timezone_name="America/Los_Angeles"))

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=history_hours)
    hist_rows = await repo.history(
        metric="pv_power_kw",
        device_type="site",
        pvs_path_id="livedata",
        start=start,
        end=end,
        limit=20000,
    )
    points = []
    for p in hist_rows:
        t = p["time"]
        points.append(
            {
                "time": t.isoformat() if hasattr(t, "isoformat") else t,
                "metric": "pv_power_kw",
                "value": float(p["value"]),
                "unit": p.get("unit") or "kW",
            }
        )

    return {
        "health": health,
        "current": current,
        "day_summary": day,
        "history_points": points,
    }


async def sync_once(settings: SyncSettings) -> None:
    if not settings.cloud_sync_token.strip():
        raise RuntimeError("CLOUD_SYNC_TOKEN is required")
    base = settings.cloud_sync_url.rstrip("/")
    url = f"{base}/v1/ingest"

    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
    try:
        repo = Repository(pool)
        payload = await build_payload(repo, settings.cloud_sync_history_hours)
        headers = {
            "Authorization": f"Bearer {settings.cloud_sync_token.strip()}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            body = res.json()
        log.info(
            "synced to %s history_points=%s",
            url,
            body.get("history_points"),
        )
    finally:
        await pool.close()


async def poll_loop(settings: SyncSettings) -> None:
    while True:
        try:
            await sync_once(settings)
        except Exception:
            log.exception("cloud sync failed")
        await asyncio.sleep(max(60, settings.cloud_sync_interval_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="Solar Monitor home → cloud sync")
    parser.add_argument("command", choices=["once", "poll"], nargs="?", default="poll")
    args = parser.parse_args()
    settings = SyncSettings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.command == "once":
        asyncio.run(sync_once(settings))
    else:
        asyncio.run(poll_loop(settings))


if __name__ == "__main__":
    main()
