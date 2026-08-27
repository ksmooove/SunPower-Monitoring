# Docker Compose notes

Default stack is **fixture-safe**: the collector does not contact the PVS.

## Services

| Service | Role |
|---------|------|
| `db` | TimescaleDB 2.19 / Postgres 16 |
| `migrate` | Applies `database/migrations/*.sql` once |
| `api` | FastAPI on port 8000 |
| `collector` | Poll + ingest (default interval 300s, source fixture) |

## Live PVS (optional)

Set in `.env`:

```
COLLECTOR_SOURCE=varserver
PVS_PASSWORD=<last-5-of-serial>
PVS_HOST=192.168.1.96
```

Prefer running the collector on the Windows host (same LAN as the PVS) until Docker networking to the PVS is verified.
