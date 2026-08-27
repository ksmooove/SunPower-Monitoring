# Solar Monitor API

FastAPI service mediating access to stored PVS measurements. Clients never talk to the PVS.

## Local run (after DB is up)

```powershell
cd c:\Users\tony\Projects\solar-monitor\apps\api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ..\..\packages\store
pip install -e ".[dev]"
$env:DATABASE_URL = "postgresql://solar:change-me-locally@127.0.0.1:5432/solar_monitor"
uvicorn solar_api.main:app --reload --port 8000
```

## Endpoints

- `GET /health` — DB + last collector run
- `GET /ready`
- `GET /v1/current` — latest livedata, meters, inverters
- `GET /v1/devices`
- `GET /v1/history?metric=pv_power_kw&hours=24`
- `GET /v1/export.csv?metric=pv_power_kw&device_type=site&pvs_path_id=livedata&hours=24`

If `API_AUTH_TOKEN` is set, send `Authorization: Bearer <token>`.
