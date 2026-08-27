# PVS6 data collector

Read-only Python collector for the home SunPower PVS6. Talks to the device only through a `PvsDataSource` adapter. Default poll interval is **300 seconds**.

## Phase 2 scope

- `VarserverDataSource` — authenticated `/auth` + `/vars` (firmware 61846 flat meter/inverter paths)
- `FixtureDataSource` — replay redacted fixtures from `fixtures/pvs6/`
- Safety: concurrency 1, timeouts, circuit breaker, no `/vars?set=`

## Setup (Windows)

```powershell
cd c:\Users\tony\Projects\solar-monitor\services\collector
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest
```

If `py` is missing, use:

`C:\Users\tony\AppData\Local\Programs\Python\Python312\python.exe`

## Fixture-only CLI (no PVS contact)

From repo root:

```powershell
cd services\collector
.\.venv\Scripts\solar-collector.exe fetch --source fixture --fixtures-dir ..\..\fixtures\pvs6
```

## Live fetch (optional; requires secrets)

Create a gitignored `.env` at the repo root with `PVS_HOST`, `PVS_USERNAME`, `PVS_PASSWORD` (last 5 of serial). Then:

```powershell
solar-collector fetch --source varserver
```

Do not run live fetch in a tight loop.
