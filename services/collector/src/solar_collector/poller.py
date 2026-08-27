from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from solar_collector.config import Settings
from solar_collector.datasource.base import PvsDataSource
from solar_collector.datasource.fixture import FixtureDataSource
from solar_collector.datasource.varserver import VarserverDataSource
from solar_store.ingest import ingest_measurements
from solar_store.repository import Repository

logger = logging.getLogger(__name__)


def build_datasource(source: str, fixtures_dir: Path, settings: Settings) -> PvsDataSource:
    if source == "fixture":
        return FixtureDataSource(fixtures_dir)
    if source == "varserver":
        if not settings.pvs_password.get_secret_value():
            raise RuntimeError("PVS_PASSWORD is required for varserver source")
        return VarserverDataSource(settings)
    raise ValueError(f"unknown source: {source}")


async def run_once(
    *,
    source: str,
    fixtures_dir: Path,
    database_url: str,
    settings: Settings | None = None,
) -> dict:
    settings = settings or Settings()
    ds = build_datasource(source, fixtures_dir, settings)
    started = datetime.now(timezone.utc)
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2)
    repo = Repository(pool)
    try:
        measurements = await ds.get_current_measurements()
        if source == "fixture":
            # Fixtures are static; stamp "now" so repeated polls create history.
            now = datetime.now(timezone.utc)
            measurements.collected_at = now
            if measurements.livedata is not None:
                measurements.livedata.pvs_time_epoch = int(now.timestamp())
                measurements.livedata.collected_at = now
            for meter in measurements.meters:
                meter.measurement_time = now
            for inv in measurements.inverters:
                inv.measurement_time = now
        async with pool.acquire() as conn:
            result = await ingest_measurements(conn, measurements)
        finished = datetime.now(timezone.utc)
        await repo.record_collector_run(
            status="ok",
            source=source,
            message=None,
            meter_count=result.meter_count,
            inverter_count=result.inverter_count,
            measurement_rows=result.measurement_rows,
            started_at=started,
            finished_at=finished,
        )
        return {
            "status": "ok",
            "measurement_rows": result.measurement_rows,
            "meter_count": result.meter_count,
            "inverter_count": result.inverter_count,
        }
    except Exception as exc:  # noqa: BLE001
        finished = datetime.now(timezone.utc)
        logger.exception("collector_run_failed")
        try:
            await repo.record_collector_run(
                status="error",
                source=source,
                message=str(exc),
                meter_count=None,
                inverter_count=None,
                measurement_rows=None,
                started_at=started,
                finished_at=finished,
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed_to_record_error_run")
        raise
    finally:
        if isinstance(ds, VarserverDataSource):
            try:
                await ds.logout()
            except Exception:  # noqa: BLE001
                logger.exception("logout_failed")
            await ds.aclose()
        await pool.close()


async def run_loop(
    *,
    source: str,
    fixtures_dir: Path,
    database_url: str,
    interval_seconds: int,
    settings: Settings | None = None,
) -> None:
    settings = settings or Settings()
    interval = max(interval_seconds, settings.pvs_poll_interval_seconds, 60)
    logger.info("collector_loop_start source=%s interval_s=%s", source, interval)
    while True:
        try:
            summary = await run_once(
                source=source,
                fixtures_dir=fixtures_dir,
                database_url=database_url,
                settings=settings,
            )
            logger.info("collector_loop_ok %s", summary)
        except Exception:  # noqa: BLE001
            logger.exception("collector_loop_iteration_failed")
        await asyncio.sleep(interval)
