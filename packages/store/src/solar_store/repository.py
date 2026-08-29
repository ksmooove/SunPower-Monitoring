from __future__ import annotations

from datetime import date, datetime
from typing import Any

import asyncpg

from solar_store.ids import HOME_SITE_ID


def compute_inverter_energy_delta(
    samples: list[tuple[datetime, float]],
    start: datetime | None,
    end: datetime,
) -> float:
    """Return kWh generated for an inverter over the selected period.

    We compare the last cumulative lifetime reading at or before the period end to the
    last reading before the period start. If no reading existed before the start, we fall
    back to the first reading within the selected window so we still show a sensible
    range total instead of a skewed negative or inflated value.
    """
    if not samples:
        return 0.0

    ordered = sorted(samples, key=lambda item: item[0])
    if start is None:
        return round(float(ordered[-1][1]), 3)

    previous: tuple[datetime, float] | None = None
    generated = 0.0
    max_power_kw = 0.36

    for ts, raw_value in ordered:
        value = float(raw_value)
        if ts < start:
            previous = (ts, value)
            continue
        if ts > end:
            break
        if previous is not None and value >= previous[1]:
            increment = value - previous[1]
            elapsed_hours = max(0.0, (ts - previous[0]).total_seconds() / 3600)
            physically_possible = max_power_kw * elapsed_hours * 1.25
            if increment <= physically_possible:
                generated += increment
        previous = (ts, value)

    return round(generated, 3)


class Repository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def health(self) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            db_ok = await conn.fetchval("SELECT 1")
            last_run = await conn.fetchrow(
                """
                SELECT id, started_at, finished_at, status, source, message,
                       meter_count, inverter_count, measurement_rows
                FROM collector_runs
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            latest = await conn.fetchval(
                "SELECT max(collected_at) FROM measurements"
            )
            inverter_seen = await conn.fetchval(
                """
                SELECT count(*) FROM devices
                WHERE site_id = $1::uuid AND device_type = 'inverter'
                """,
                HOME_SITE_ID,
            )
        return {
            "database_ok": db_ok == 1,
            "latest_measurement_at": latest.isoformat() if latest else None,
            "inverter_devices": int(inverter_seen or 0),
            "last_collector_run": dict(last_run) if last_run else None,
        }

    async def current_overview(self) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                                WITH latest_collection AS (
                                        SELECT max(m.collected_at) AS collected_at
                                        FROM measurements m
                                        JOIN devices d ON d.id = m.device_id
                                        WHERE d.site_id = $1::uuid
                                            AND d.device_type = 'site'
                                            AND d.pvs_path_id = 'livedata'
                                )
                                SELECT m.metric, m.value, m.unit, m.time, m.collected_at, m.quality, m.source
                                FROM measurements m
                                JOIN devices d ON d.id = m.device_id
                                CROSS JOIN latest_collection latest
                                WHERE d.site_id = $1::uuid
                                    AND d.device_type = 'site'
                                    AND d.pvs_path_id = 'livedata'
                                    AND m.collected_at = latest.collected_at
                                ORDER BY m.metric
                """,
                HOME_SITE_ID,
            )
            inverters = await conn.fetch(
                """
                SELECT d.pvs_path_id, d.name, d.model, d.last_seen_at,
                       m.value AS power_kw, m.time AS power_time, m.collected_at
                FROM devices d
                LEFT JOIN LATERAL (
                    SELECT value, time, collected_at
                    FROM measurements mm
                    WHERE mm.device_id = d.id AND mm.metric = 'power_kw'
                    ORDER BY mm.time DESC
                    LIMIT 1
                ) m ON TRUE
                WHERE d.site_id = $1::uuid AND d.device_type = 'inverter'
                ORDER BY (d.pvs_path_id)::int
                """,
                HOME_SITE_ID,
            )
            meters = await conn.fetch(
                """
                SELECT d.pvs_path_id, d.name, d.model, d.last_seen_at,
                       m.value AS power_kw, m.time AS power_time
                FROM devices d
                LEFT JOIN LATERAL (
                    SELECT value, time
                    FROM measurements mm
                    WHERE mm.device_id = d.id AND mm.metric = 'power_kw'
                    ORDER BY mm.time DESC
                    LIMIT 1
                ) m ON TRUE
                WHERE d.site_id = $1::uuid AND d.device_type = 'meter'
                ORDER BY (d.pvs_path_id)::int
                """,
                HOME_SITE_ID,
            )

        livedata = {r["metric"]: {
            "value": r["value"],
            "unit": r["unit"],
            "time": r["time"].isoformat(),
            "collected_at": r["collected_at"].isoformat(),
            "quality": r["quality"],
            "source": r["source"],
        } for r in rows}

        return {
            "site_id": HOME_SITE_ID,
            "livedata": livedata,
            "meters": [dict(r) for r in meters],
            "inverters": [dict(r) for r in inverters],
            "inverter_power_kw_sum": round(
                sum(float(r["power_kw"]) for r in inverters if r["power_kw"] is not None),
                6,
            ),
        }

    async def history(
        self,
        *,
        metric: str,
        device_type: str | None,
        pvs_path_id: str | None,
        start: datetime,
        end: datetime,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        if limit > 20000:
            limit = 20000
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.time, m.value, m.unit, m.quality, m.source, m.collected_at,
                       d.device_type, d.pvs_path_id, d.name
                FROM measurements m
                JOIN devices d ON d.id = m.device_id
                WHERE d.site_id = $1::uuid
                  AND m.metric = $2
                  AND m.time >= $3
                  AND m.time < $4
                  AND ($5::text IS NULL OR d.device_type = $5)
                  AND ($6::text IS NULL OR d.pvs_path_id = $6)
                ORDER BY m.time ASC
                LIMIT $7
                """,
                HOME_SITE_ID,
                metric,
                start,
                end,
                device_type,
                pvs_path_id,
                limit,
            )
        return [dict(r) for r in rows]

    async def devices(self) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, device_type, pvs_path_id, model, name, rated_watts,
                       grid_row, grid_col, enabled, first_seen_at, last_seen_at
                FROM devices
                WHERE site_id = $1::uuid
                ORDER BY device_type, (CASE WHEN pvs_path_id ~ '^[0-9]+$' THEN pvs_path_id::int ELSE 0 END)
                """,
                HOME_SITE_ID,
            )
        return [dict(r) for r in rows]

    async def update_device_layout(
        self,
        device_id: str,
        *,
        grid_row: int | None,
        grid_col: int | None,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE devices
                SET grid_row = COALESCE($2, grid_row),
                    grid_col = COALESCE($3, grid_col),
                    name = COALESCE($4, name)
                WHERE id = $1::uuid AND site_id = $5::uuid AND device_type = 'inverter'
                RETURNING id, device_type, pvs_path_id, model, name, rated_watts,
                          grid_row, grid_col, enabled, first_seen_at, last_seen_at
                """,
                device_id,
                grid_row,
                grid_col,
                name,
                HOME_SITE_ID,
            )
        return dict(row) if row else None

    async def inverter_playback(
        self,
        *,
        start: datetime,
        end: datetime,
        limit: int = 50000,
    ) -> dict[str, Any]:
        """Time-ordered inverter power samples for heatmap playback."""
        if limit > 100000:
            limit = 100000
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT m.time, d.pvs_path_id, m.value AS power_kw
                FROM measurements m
                JOIN devices d ON d.id = m.device_id
                WHERE d.site_id = $1::uuid
                  AND d.device_type = 'inverter'
                  AND m.metric = 'power_kw'
                  AND m.time >= $2
                  AND m.time < $3
                ORDER BY m.time ASC, (d.pvs_path_id)::int ASC
                LIMIT $4
                """,
                HOME_SITE_ID,
                start,
                end,
                limit,
            )
            devices = await conn.fetch(
                """
                SELECT pvs_path_id, name, grid_row, grid_col
                FROM devices
                WHERE site_id = $1::uuid AND device_type = 'inverter'
                ORDER BY (pvs_path_id)::int
                """,
                HOME_SITE_ID,
            )

        frames_map: dict[str, dict[str, float]] = {}
        max_kw = 0.0
        for r in rows:
            key = r["time"].isoformat()
            bucket = frames_map.setdefault(key, {})
            val = float(r["power_kw"])
            bucket[str(r["pvs_path_id"])] = val
            if val > max_kw:
                max_kw = val

        frames = [{"time": t, "powers": powers} for t, powers in frames_map.items()]
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "frame_count": len(frames),
            "max_kw": max_kw,
            "devices": [dict(d) for d in devices],
            "frames": frames,
        }

    async def inverter_energy_summary(
    self,
    *,
    start: datetime | None,
    end: datetime,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT d.pvs_path_id, m.time, m.value
                FROM devices d
                JOIN measurements m ON m.device_id = d.id
                WHERE d.site_id = $1::uuid
                  AND d.device_type = 'inverter'
                  AND m.metric = 'lifetime_energy_kwh'
                  AND m.time <= $2
                ORDER BY d.pvs_path_id::int ASC, m.time ASC
                """,
                HOME_SITE_ID,
                end,
            )

        by_inverter: dict[str, list[tuple[datetime, float]]] = {}
        for row in rows:
            pvs_path_id = str(row["pvs_path_id"])
            by_inverter.setdefault(pvs_path_id, []).append((row["time"], float(row["value"])))

        values: dict[str, float | None] = {}
        for pvs_path_id, samples in by_inverter.items():
            if not samples:
                values[pvs_path_id] = None
                continue

            if start is None:
                # Lifetime counters can briefly report a lower value after a
                # device reset. Preserve the highest observed lifetime total.
                values[pvs_path_id] = round(max(value for _, value in samples), 3)
            else:
                values[pvs_path_id] = compute_inverter_energy_delta(samples, start, end)

        return {
            "start": start.isoformat() if start else None,
            "end": end.isoformat(),
            "values_kwh": values,
            "max_kwh": max((v for v in values.values() if v is not None), default=0.0),
        }

    async def day_energy_summary(
        self,
        *,
        timezone_name: str = "America/Los_Angeles",
    ) -> dict[str, Any]:
        """Calendar-day energy from cumulative counters (measured deltas)."""
        from datetime import time as time_of_day
        from datetime import timezone as tz_utc
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(timezone_name)
        now_local = datetime.now(zone)
        day_start_local = datetime.combine(now_local.date(), time_of_day.min, tzinfo=zone)
        start = day_start_local.astimezone(tz_utc.utc)
        end = now_local.astimezone(tz_utc.utc)

        async with self._pool.acquire() as conn:
            first_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (m.metric)
                    m.metric, m.value, m.time, m.unit
                FROM measurements m
                JOIN devices d ON d.id = m.device_id
                WHERE d.site_id = $1::uuid
                  AND d.device_type = 'site'
                  AND d.pvs_path_id = 'livedata'
                  AND m.metric IN ('pv_energy_kwh', 'net_energy_kwh', 'site_load_energy_kwh')
                  AND m.time >= $2
                  AND m.time <= $3
                ORDER BY m.metric, m.time ASC
                """,
                HOME_SITE_ID,
                start,
                end,
            )
            last_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (m.metric)
                    m.metric, m.value, m.time, m.unit
                FROM measurements m
                JOIN devices d ON d.id = m.device_id
                WHERE d.site_id = $1::uuid
                  AND d.device_type = 'site'
                  AND d.pvs_path_id = 'livedata'
                  AND m.metric IN ('pv_energy_kwh', 'net_energy_kwh', 'site_load_energy_kwh')
                  AND m.time >= $2
                  AND m.time <= $3
                ORDER BY m.metric, m.time DESC
                """,
                HOME_SITE_ID,
                start,
                end,
            )

        first_map = {r["metric"]: r for r in first_rows}
        last_map = {r["metric"]: r for r in last_rows}

        def delta(metric: str) -> dict[str, Any] | None:
            a = first_map.get(metric)
            b = last_map.get(metric)
            if not a or not b:
                return None
            if a["time"] == b["time"]:
                return {
                    "kwh": 0.0,
                    "insufficient_samples": True,
                    "first_at": a["time"].isoformat(),
                    "last_at": b["time"].isoformat(),
                }
            return {
                "kwh": float(b["value"]) - float(a["value"]),
                "insufficient_samples": False,
                "first_at": a["time"].isoformat(),
                "last_at": b["time"].isoformat(),
            }

        pv = delta("pv_energy_kwh")
        net = delta("net_energy_kwh")
        load = delta("site_load_energy_kwh")

        # Sign convention observed on this site: negative net power => export.
        # A negative net_energy delta therefore means exported to grid today.
        grid_kwh = None
        grid_direction = None
        if net and not net.get("insufficient_samples"):
            raw = float(net["kwh"])
            if raw < 0:
                grid_kwh = abs(raw)
                grid_direction = "export"
            elif raw > 0:
                grid_kwh = raw
                grid_direction = "import"
            else:
                grid_kwh = 0.0
                grid_direction = "neutral"

        return {
            "timezone": timezone_name,
            "local_date": now_local.date().isoformat(),
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "generated_kwh": None if not pv else max(0.0, float(pv["kwh"])),
            "generated_insufficient_samples": bool(pv and pv.get("insufficient_samples")),
            "grid_kwh": grid_kwh,
            "grid_direction": grid_direction,
            "grid_insufficient_samples": bool(net and net.get("insufficient_samples")),
            "home_load_kwh": None if not load else max(0.0, float(load["kwh"])),
            "home_load_insufficient_samples": bool(load and load.get("insufficient_samples")),
            "quality": "measured",
            "method": "cumulative_counter_delta",
        }

    #KP modified
    async def production_energy_by_day(
        self,
        *,
        start_date: date | None,
        end_date: date,
        timezone_name: str,
    ) -> list[dict[str, Any]]:
        """
        Return generated solar energy for each local calendar day.

        Energy is calculated from the pv_energy_kwh cumulative counter:

            last reading of local day
            -
            first reading of local day
            =
            generated kWh for that day
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH samples AS (
                    SELECT
                        (m.time AT TIME ZONE $2)::date AS local_date,
                        m.time,
                        m.value
                    FROM measurements m
                    JOIN devices d ON d.id = m.device_id
                    WHERE d.site_id = $1::uuid
                      AND d.device_type = 'site'
                      AND d.pvs_path_id = 'livedata'
                      AND m.metric = 'pv_energy_kwh'
                      AND ($3::date IS NULL OR (m.time AT TIME ZONE $2)::date >= $3::date)
                      AND (m.time AT TIME ZONE $2)::date <= $4::date
                ),
                ranked AS (
                    SELECT
                        local_date,
                        time,
                        value,
                        ROW_NUMBER() OVER (
                            PARTITION BY local_date
                            ORDER BY time ASC
                        ) AS first_rank,
                        ROW_NUMBER() OVER (
                            PARTITION BY local_date
                            ORDER BY time DESC
                        ) AS last_rank
                    FROM samples
                )
                SELECT
                    local_date,
                    MAX(value) FILTER (WHERE first_rank = 1) AS first_value,
                    MAX(value) FILTER (WHERE last_rank = 1) AS last_value,
                    MAX(time) FILTER (WHERE first_rank = 1) AS first_at,
                    MAX(time) FILTER (WHERE last_rank = 1) AS last_at,
                    COUNT(*) AS sample_count
                FROM ranked
                GROUP BY local_date
                ORDER BY local_date ASC
                """,
                HOME_SITE_ID,
                timezone_name,
                start_date,
                end_date,
            )
            historical_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (d.local_date)
                    d.local_date, d.energy_kwh, d.max_power_kw
                FROM historical_report_days d
                JOIN historical_reports r ON r.id = d.report_id
                WHERE ($1::date IS NULL OR d.local_date >= $1::date)
                  AND d.local_date <= $2::date
                ORDER BY d.local_date, r.period_end DESC
                """,
                start_date,
                end_date,
            )

        result: list[dict[str, Any]] = []

        historical_by_date = {
            row["local_date"]: row for row in historical_rows
        }

        for row in rows:
            first_value = row["first_value"]
            last_value = row["last_value"]
            first_at = row["first_at"]
            last_at = row["last_at"]

            sufficient_samples = (
                first_value is not None
                and last_value is not None
                and first_at is not None
                and last_at is not None
                and first_at != last_at
            )

            generated_kwh = None

            if sufficient_samples:
                generated_kwh = max(
                    0.0,
                    float(last_value) - float(first_value),
                )

            local_date = row["local_date"]
            historical = historical_by_date.pop(local_date, None)
            if generated_kwh is None and historical is not None:
                generated_kwh = float(historical["energy_kwh"])
                sufficient_samples = True

            result.append({
                "date": local_date.isoformat(),
                "generated_kwh": generated_kwh,
                "insufficient_samples": not sufficient_samples,
                "sample_count": int(row["sample_count"]),
                "first_at": first_at.isoformat() if first_at else None,
                "last_at": last_at.isoformat() if last_at else None,
            })

        for local_date, historical in sorted(historical_by_date.items()):
            result.append({
                "date": local_date.isoformat(),
                "generated_kwh": float(historical["energy_kwh"]),
                "insufficient_samples": False,
                "sample_count": 1,
                "first_at": None,
                "last_at": None,
            })

        result.sort(key=lambda point: point["date"])

        return result


    #lifetime
    async def lifetime_pv_energy(self) -> float | None:
        async with self._pool.acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT MAX(value)
                FROM measurements
                WHERE metric = 'pv_energy_kwh'
                """
            )

        return float(value) if value is not None else None
    async def record_collector_run(
        self,
        *,
        status: str,
        source: str,
        message: str | None,
        meter_count: int | None,
        inverter_count: int | None,
        measurement_rows: int | None,
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO collector_runs (
                    site_id, started_at, finished_at, status, source, message,
                    meter_count, inverter_count, measurement_rows
                )
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                HOME_SITE_ID,
                started_at,
                finished_at,
                status,
                source,
                message,
                meter_count,
                inverter_count,
                measurement_rows,
            )
