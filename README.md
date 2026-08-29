# Solar Monitor

**Version 1.0** — Local SunPower PVS6 monitoring at home, plus a cloud read replica for the Android app.

This project collects telemetry from **your own** PVS6 on **your own** LAN, stores history in a local time-series database, and serves a web UI. A DigitalOcean droplet holds a **read-only sync** so the phone can use HTTPS away from home. The PVS6 is never exposed to browsers or phones—the collector and APIs mediate all access.

## Status

**v1.0 — home stack + cloud replica + Android.**

| Piece | Where |
|-------|--------|
| Web UI (PWA) | http://127.0.0.1:3080 |
| Home API | http://127.0.0.1:8000 (`/health`, `/v1/*`) |
| Cloud API | `https://solar.blackmagicsoftware.net` (read replica) |
| Android | [`apps/android`](apps/android/) → cloud HTTPS |
| Database | TimescaleDB on port 5432 (home); synced slice on droplet |
| Collector | Docker service; poll interval **300s** |
| Cloud sync | Compose profile `cloud-sync` (home → droplet ingest) |

Compose defaults to **fixture** replay (safe, no PVS contact). Live collection uses `COLLECTOR_SOURCE=varserver` plus `PVS_PASSWORD` in a gitignored `.env`.

## Architecture

```
PVS6 (LAN) → collector (read-only) → TimescaleDB (home)
                                         │
                                         │ cloud-sync (HTTPS ingest)
                                         ▼
                              TimescaleDB + API (DigitalOcean)
                                         │
                    PWA (home) ← home API    Android ← cloud API (Bearer)
```

Home is the source of truth. The droplet is a **read replica / mobile API**, not a second collector. Overview: [docs/remote-access.md](docs/remote-access.md).

---

## 1. Local Windows stack

**Prerequisites:** Docker Desktop running on Windows.

```powershell
cd <path-to-sunpowermonitor>
Copy-Item .env.example .env
# Edit .env: set POSTGRES_PASSWORD and SITE_TIMEZONE at minimum; for live PVS see below
docker compose up --build -d
```

Then open:

- **App:** http://127.0.0.1:3080
- **API health:** http://127.0.0.1:8000/health

### Import SunPower PDF reports on the runtime workstation

Historical monthly reports can be imported without changing live collector data. The importer stores
the report totals and daily rows in the database, and production history uses those values only when
needed.

By default, report rows are used as a fallback for dates where the collector has no valid cumulative
samples. If you want a report to override the collector for the same local day, pass
`--prefer-report` when importing:

```powershell
.\.venv\Scripts\python.exe scripts\import_sunpower_reports.py C:\path\to\reports --database-url $env:DATABASE_URL --prefer-report
```

That flag does not delete or rewrite collector measurements. It only marks the imported report rows as
preferred so the app prefers the report day values during reads for matching dates.

The PDF files and database stay on the workstation that runs Docker. They do not need to be copied
to the build machine or committed. On that workstation, pull the code and start the stack so the
historical-report migrations run:

```powershell
git pull origin <your-branch>
docker compose up -d --build

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r scripts\requirements.txt
$env:DATABASE_URL = "postgresql://solar:YOUR_PASSWORD@127.0.0.1:5432/solar_monitor"
.\.venv\Scripts\python.exe scripts\import_sunpower_reports.py C:\path\to\reports --database-url $env:DATABASE_URL
```

The command is safe to rerun. It expects text-extractable PDFs whose daily rows contain date,
energy kWh, and maximum AC power kW, like the SunPower monthly report format. The importer stores
site-level daily production; these reports do not contain enough information to reconstruct
individual panel production.

You can check the service health and current values after importing:

```powershell
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8000/v1/current
```

Stop:

```powershell
docker compose down
```

### Live varserver (optional)

`.env` is gitignored. To poll the real PVS (read-only, 300s):

```env
COLLECTOR_SOURCE=varserver
PVS_HOST=192.168.1.96
PVS_USERNAME=ssm_owner
PVS_PASSWORD=xxxxx
PVS_POLL_INTERVAL_SECONDS=300
```

`PVS_PASSWORD` is the **last 5 characters of the PVS serial** (SunStrong owner auth).

```powershell
docker compose up -d collector
docker compose logs -f collector
```

Expect `source=varserver` and `collector_loop_ok`. To return to safe fixtures: set `COLLECTOR_SOURCE=fixture` and recreate the collector.

### Web UI development

```powershell
cd apps\web
npm install
npm run dev
```

http://127.0.0.1:5173 proxies `/api` to the API on :8000.

---

## 2. Cloud read replica (phone backend)

Phones do **not** talk to the home PC or the PVS. They use the DigitalOcean HTTPS API fed by home sync.

| Role | Token / secret |
|------|----------------|
| Phone / Android | `API_AUTH_TOKEN` on the droplet |
| Home → cloud ingest | `CLOUD_SYNC_TOKEN` (same value in home `.env` and droplet `.env`) |

Setup and deploy:

1. [docs/cloud-droplet-setup.md](docs/cloud-droplet-setup.md) — provision Ubuntu droplet, Docker, Caddy, Timescale
2. [docs/cloud-deploy.md](docs/cloud-deploy.md) — deploy/update the cloud API
3. [docs/cloud-remaining-steps.md](docs/cloud-remaining-steps.md) — command-by-command checklist (if starting from scratch)

On the **home** PC, after the droplet is healthy, enable sync:

```env
# in home .env
CLOUD_SYNC_URL=https://solar.blackmagicsoftware.net
CLOUD_SYNC_TOKEN=<same as droplet CLOUD_SYNC_TOKEN>
CLOUD_SYNC_INTERVAL_SECONDS=300
```

```powershell
docker compose --profile cloud-sync up -d --build cloud-sync
docker compose logs -f cloud-sync
```

Expect successful `POST /v1/ingest` (HTTP 200).

---

## 3. Android app

Native Kotlin + Jetpack Compose client. Details: [`apps/android/README.md`](apps/android/README.md).

**Prerequisites:** JDK 17, Android SDK (or Android Studio), cloud API live with synced data, phone Bearer = droplet `API_AUTH_TOKEN`.

### Release APK (signed)

```powershell
cd apps\android
Copy-Item key.properties.example key.properties
# Edit key.properties: storeFile, storePassword, keyAlias, keyPassword
# (project default keystore path example: C:\dev\SIGNKEYS\upload-keystore.jks)
.\gradlew.bat :app:assembleRelease
```

Install: `app\build\outputs\apk\release\app-release.apk`

### In-app settings

| Field | Value |
|-------|--------|
| API base URL | `https://solar.blackmagicsoftware.net` |
| Bearer token | Droplet `API_AUTH_TOKEN` (**not** `CLOUD_SYNC_TOKEN`) |

Live tab shows the same house power-flow scene as the web UI (portrait / landscape by orientation).

---

## What “Home Assistant” means here

[Home Assistant](https://www.home-assistant.io/) is optional home-automation software. This stack is **standalone** and does not require HA. An HA/MQTT integration may come later.

## Repository layout

```
apps/web/              PWA (Vite + React)
apps/api/              Home FastAPI
apps/cloud-api/        Cloud FastAPI (read + ingest)
apps/android/          Kotlin Compose phone app
services/collector     Read-only PVS collector
services/cloud-sync    Home → cloud snapshot sync
packages/store         Shared DB ingest/query helpers
database/              SQL migrations + seed
fixtures/pvs6/         Redacted response fixtures
infrastructure/docker  Home Dockerfiles
infrastructure/cloud   Droplet Compose + Caddy
docs/                  Architecture, cloud, safety, ADRs
docker-compose.yml
.env.example           Template (no secrets)
```

## Safety

- Read-only PVS interaction unless you explicitly authorize otherwise.
- Default / recommended poll interval: **300 seconds**.
- No subnet scans, firmware changes, or uploading captures/serials.
- Do not expose the PVS or unauthenticated home APIs to the public internet.
- Cloud API is authenticated (Bearer); ingest uses a separate sync token.
- See [SECURITY.md](SECURITY.md) and [docs/polling-safety.md](docs/polling-safety.md).

## Publishing a release (v1.0+)

Docker images ship from CI on a `v*` tag; the **signed APK is built on your PC** with your upload keystore (never uploaded to Actions secrets).

```powershell
.\scripts\publish-release.ps1 -Version 1.0.0
```

Details: [docs/releasing.md](docs/releasing.md).

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/releasing.md](docs/releasing.md) | Tag release, GHCR images, local signed APK |
| [docs/architecture.md](docs/architecture.md) | System design |
| [docs/data-model.md](docs/data-model.md) | Schema and metrics |
| [docs/remote-access.md](docs/remote-access.md) | Mobile / cloud access overview |
| [docs/cloud-droplet-setup.md](docs/cloud-droplet-setup.md) | DigitalOcean droplet bootstrap |
| [docs/cloud-deploy.md](docs/cloud-deploy.md) | Deploy / update cloud API |
| [docs/cloud-remaining-steps.md](docs/cloud-remaining-steps.md) | End-to-end cloud + Android checklist |
| [apps/android/README.md](apps/android/README.md) | Android build and settings |
| [docs/mobile-ui.md](docs/mobile-ui.md) | PWA screens |
| [docs/pvs6-discovery.md](docs/pvs6-discovery.md) | Observed PVS interfaces |
| [docs/prior-art.md](docs/prior-art.md) | Related projects and licenses |
| [docs/polling-safety.md](docs/polling-safety.md) | Hardware protection policy |
| [docs/backup-restore.md](docs/backup-restore.md) | Database backup/restore |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## License

[MIT](LICENSE). Third-party projects retain their own licenses; see [docs/prior-art.md](docs/prior-art.md).
