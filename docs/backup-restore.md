# Backup and restore

## Docker volume backup (Timescale/Postgres)

```powershell
cd c:\Users\tony\Projects\solar-monitor
New-Item -ItemType Directory -Force -Path backups | Out-Null
docker compose exec -T db pg_dump -U solar -d solar_monitor -Fc -f /tmp/solar_monitor.dump
docker compose cp db:/tmp/solar_monitor.dump backups/solar_monitor.dump
```

`backups/` is gitignored.

## Restore

```powershell
docker compose up -d db
# wait until healthy
docker compose cp backups/solar_monitor.dump db:/tmp/solar_monitor.dump
docker compose exec db pg_restore -U solar -d solar_monitor --clean --if-exists /tmp/solar_monitor.dump
```

## Notes

- Prefer dumping before upgrading images.
- After schema-only restore, re-run migrations if needed, then `solar-collector ingest-once --source fixture` for demo data.
