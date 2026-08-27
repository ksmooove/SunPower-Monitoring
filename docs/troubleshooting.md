# Troubleshooting

## Stack will not start

- Ensure Docker Desktop is running.
- `docker compose ps` and `docker compose logs <service>`.
- Port conflicts: API **8000**, web **3080**, Postgres **5432**. Change via `.env` (`API_PORT`, `WEB_PORT`).

## UI loads but data is empty or stale

- Check http://127.0.0.1:8000/health — `database_ok`, `last_collector_run`.
- Fixture mode repeats the same sample until enough polls accumulate for the day chart.
- Live mode: confirm `.env` has `COLLECTOR_SOURCE=varserver` and a correct `PVS_PASSWORD`, then `docker compose up -d collector` and inspect logs.

## Collector cannot reach PVS (varserver)

- PVS and PC must be on the same LAN; AP client isolation can block device-to-device traffic.
- From the host: `Test-NetConnection 192.168.1.96 -Port 443`.
- Auth failures: password is last 5 characters of the PVS serial (owner auth).
- If Docker networking fails, run `solar-collector ingest-once --source varserver` on the host against `DATABASE_URL` pointing at `127.0.0.1:5432`.

## Migrate container fails with `set: illegal option`

- `database/migrate.sh` must use LF line endings (see `.gitattributes`). Rebuild: `docker compose build migrate`.

## Web returns 404 on port 8080

- This project’s UI defaults to **3080** (8080 is often taken on Windows). Use http://127.0.0.1:3080.

## Safety fallback

To stop live PVS traffic immediately:

```env
COLLECTOR_SOURCE=fixture
```

```powershell
docker compose up -d collector
```
