# ADR 0001: Overall architecture choice

- **Status:** Accepted
- **Date:** 2026-07-13
- **Deciders:** Site owner + technical lead (this project)

## Context

We need a durable, cloud-free PVS6 monitoring system with per-panel history, a phone-friendly UI, and strict hardware safety. The repo is greenfield. Firmware is **61846** (official varserver local API available). The always-on host is currently a Windows PC; deployment must remain portable. Home Assistant is not required.

Alternatives considered:

1. **Home Assistant as collector** (e.g. ha-esunpower / pvs-hass) with a thin custom UI later.
2. **Custom mediated stack:** Python collector → TimescaleDB → FastAPI → PWA.
3. **Single-process SQLite MVP** (collector + API + DB in one process).

## Decision

Adopt **option 2**: a custom mediated stack with protocol adapters behind `PvsDataSource`, PostgreSQL + TimescaleDB, FastAPI, and a responsive PWA for the MVP. Defer React Native/Expo. Do not require Home Assistant.

Lock related defaults:

| Decision | Choice |
|----------|--------|
| Primary PVS interface | Authenticated varserver (`/auth`, `/vars`) |
| Legacy `dl_cgi` | Secondary / sparingly |
| Default poll interval | 300 seconds |
| Max concurrency to PVS | 1 |
| Database | PostgreSQL + TimescaleDB |
| API | FastAPI |
| UI MVP | PWA |
| Remote hosting | Portable Compose; public VPS only with VPN/tunnel—never direct PVS exposure |

## Consequences

- **Positive:** Full control of polling safety, schema, backups, panel layout UX, and export; clear ownership; CI without live PVS via fixtures.
- **Negative:** More engineering than installing an HA integration; must reimplement (or carefully wrap) auth/vars client behavior already present in pypvs / community projects.
- **Follow-ups:** Phase 1 discovery plan; Phase 2 collector with `VarserverDataSource`; optional MQTT/HA later without making HA the core.
