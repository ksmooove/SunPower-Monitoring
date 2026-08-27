# Architecture Decision Record 0002: Measurement schema and units

- **Status:** Accepted
- **Date:** 2026-07-13

## Context

Phase 3 needs durable storage for site livedata, two meters, and 44 inverters with idempotent ingestion.

## Decision

1. PostgreSQL + TimescaleDB hypertable `measurements` keyed by `(time, device_id, metric, source)`.
2. Preserve **source units**: power as `kW`, energy as `kWh`, voltage `V`, current `A`, frequency `Hz`, temperature `°C`. Do not invent Wh by integrating power.
3. Represent site livedata as a synthetic `devices` row (`device_type=site`, `pvs_path_id=livedata`).
4. Do not store full serial numbers in the database; device identity is `(supervisor_id, device_type, pvs_path_id)`.
5. Default Docker collector source is `fixture` so compose brings up safely without PVS credentials; live `varserver` is opt-in via env.

## Consequences

- Queries compare like-with-like units; UI converts for display as needed.
- Panel layout columns (`grid_row`, `grid_col`) exist for Phase 4 heatmap editing.
- Inverter power sum may differ from livedata `pv_p`; both are stored separately.
