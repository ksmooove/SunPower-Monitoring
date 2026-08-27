from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg

from solar_store.ids import HOME_SITE_ID, PRIMARY_SUPERVISOR_ID


@dataclass
class IngestResult:
    measurement_rows: int
    meter_count: int
    inverter_count: int
    devices_upserted: int


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _measurement_time(livedata_epoch: int | None, collected_at: datetime) -> datetime:
    if livedata_epoch is not None and livedata_epoch > 0:
        # Guard against absurd future epochs from bad fixtures/devices
        candidate = datetime.fromtimestamp(livedata_epoch, tz=timezone.utc)
        if candidate.year >= 2020:
            return candidate
    return _utc(collected_at)


async def _upsert_device(
    conn: asyncpg.Connection,
    *,
    device_type: str,
    pvs_path_id: str,
    model: str | None,
    name: str | None,
    rated_watts: int | None,
    seen_at: datetime,
) -> UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO devices (
            site_id, supervisor_id, device_type, pvs_path_id, model, name, rated_watts,
            first_seen_at, last_seen_at
        )
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $8)
        ON CONFLICT (supervisor_id, device_type, pvs_path_id) DO UPDATE
        SET model = COALESCE(EXCLUDED.model, devices.model),
            name = COALESCE(EXCLUDED.name, devices.name),
            rated_watts = COALESCE(EXCLUDED.rated_watts, devices.rated_watts),
            last_seen_at = EXCLUDED.last_seen_at
        RETURNING id
        """,
        HOME_SITE_ID,
        PRIMARY_SUPERVISOR_ID,
        device_type,
        pvs_path_id,
        model,
        name,
        rated_watts,
        seen_at,
    )
    assert row is not None
    return row["id"]


async def ingest_measurements(conn: asyncpg.Connection, payload: Any) -> IngestResult:
    """Idempotent ingest of a solar_collector CurrentMeasurements-like object.

    Accepts either a pydantic model (attribute access) or a plain namespace with
    the same field names used by solar_collector.models.CurrentMeasurements.
    """
    collected_at = _utc(getattr(payload, "collected_at", None))
    parser_version = getattr(payload, "parser_version", "1") or "1"
    livedata = getattr(payload, "livedata", None)
    meters = list(getattr(payload, "meters", []) or [])
    inverters = list(getattr(payload, "inverters", []) or [])

    rows: list[tuple[Any, ...]] = []
    devices_upserted = 0

    async with conn.transaction():
        await conn.execute(
            """
            UPDATE supervisors
            SET last_seen_at = $2,
                software_version = COALESCE($3, software_version)
            WHERE id = $1::uuid
            """,
            PRIMARY_SUPERVISOR_ID,
            collected_at,
            None,
        )

        # Site livedata device (seeded id, but upsert path keeps last_seen fresh)
        site_id = await _upsert_device(
            conn,
            device_type="site",
            pvs_path_id="livedata",
            model="PVS6",
            name="Site totals",
            rated_watts=None,
            seen_at=collected_at,
        )
        devices_upserted += 1

        if livedata is not None:
            t = _measurement_time(getattr(livedata, "pvs_time_epoch", None), collected_at)
            source = getattr(livedata, "source", "varserver.livedata")
            quality = str(getattr(livedata, "quality", "measured"))
            pairs = [
                ("pv_power_kw", getattr(livedata, "pv_power_kw", None), "kW"),
                ("pv_energy_kwh", getattr(livedata, "pv_energy_kwh", None), "kWh"),
                ("net_power_kw", getattr(livedata, "net_power_kw", None), "kW"),
                ("net_energy_kwh", getattr(livedata, "net_energy_kwh", None), "kWh"),
                ("site_load_power_kw", getattr(livedata, "site_load_power_kw", None), "kW"),
                ("site_load_energy_kwh", getattr(livedata, "site_load_energy_kwh", None), "kWh"),
            ]
            for metric, value, unit in pairs:
                if value is None:
                    continue
                rows.append(
                    (
                        t,
                        site_id,
                        metric,
                        float(value),
                        unit,
                        quality,
                        source,
                        parser_version,
                        collected_at,
                    )
                )

        for meter in meters:
            idx = int(getattr(meter, "meter_index"))
            model = getattr(meter, "model", None)
            device_id = await _upsert_device(
                conn,
                device_type="meter",
                pvs_path_id=str(idx),
                model=model,
                name=f"Meter {idx}",
                rated_watts=None,
                seen_at=collected_at,
            )
            devices_upserted += 1
            t = _utc(getattr(meter, "measurement_time", None) or collected_at)
            source = getattr(meter, "source", "varserver.meter")
            quality = str(getattr(meter, "quality", "measured"))
            for metric, value, unit in [
                ("power_kw", getattr(meter, "power_kw", None), "kW"),
                ("net_energy_kwh", getattr(meter, "net_energy_kwh", None), "kWh"),
                ("pos_energy_kwh", getattr(meter, "pos_energy_kwh", None), "kWh"),
                ("neg_energy_kwh", getattr(meter, "neg_energy_kwh", None), "kWh"),
                ("voltage_v", getattr(meter, "voltage_v", None), "V"),
                ("freq_hz", getattr(meter, "freq_hz", None), "Hz"),
            ]:
                if value is None:
                    continue
                rows.append(
                    (
                        t,
                        device_id,
                        metric,
                        float(value),
                        unit,
                        quality,
                        source,
                        parser_version,
                        collected_at,
                    )
                )

        for inv in inverters:
            idx = int(getattr(inv, "inverter_index"))
            model = getattr(inv, "model", None)
            device_id = await _upsert_device(
                conn,
                device_type="inverter",
                pvs_path_id=str(idx),
                model=model,
                name=f"Inverter {idx}",
                rated_watts=360,
                seen_at=collected_at,
            )
            devices_upserted += 1
            t = _utc(getattr(inv, "measurement_time", None) or collected_at)
            source = getattr(inv, "source", "varserver.inverter")
            quality = str(getattr(inv, "quality", "measured"))
            for metric, value, unit in [
                ("power_kw", getattr(inv, "power_kw", None), "kW"),
                ("lifetime_energy_kwh", getattr(inv, "lifetime_energy_kwh", None), "kWh"),
                ("voltage_v", getattr(inv, "voltage_v", None), "V"),
                ("current_a", getattr(inv, "current_a", None), "A"),
                ("freq_hz", getattr(inv, "freq_hz", None), "Hz"),
                ("heatsink_c", getattr(inv, "heatsink_c", None), "°C"),
            ]:
                if value is None:
                    continue
                rows.append(
                    (
                        t,
                        device_id,
                        metric,
                        float(value),
                        unit,
                        quality,
                        source,
                        parser_version,
                        collected_at,
                    )
                )

        if rows:
            await conn.executemany(
                """
                INSERT INTO measurements (
                    time, device_id, metric, value, unit, quality, source, parser_version, collected_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (time, device_id, metric, source) DO NOTHING
                """,
                rows,
            )

    return IngestResult(
        measurement_rows=len(rows),
        meter_count=len(meters),
        inverter_count=len(inverters),
        devices_upserted=devices_upserted,
    )
