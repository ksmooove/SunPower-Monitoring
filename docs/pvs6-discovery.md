# PVS6 discovery log (sanitized)

**Status:** Phase 2 discovery + collector scaffolding complete (2026-07-13).

**Redaction rules:** Do not commit full serial numbers, MAC addresses, Wi-Fi SSIDs/passwords, tokens, cookies, or unredacted payloads. Raw responses live under gitignored `docs/discovery/private/`. Commit-safe copies in `fixtures/pvs6/`.

---

## Operator-provided facts (2026-07-13)

| Item | Value | Confidence |
|------|--------|------------|
| Model | SunPower PVS6 | High |
| Firmware build | **61846** (`SWVER` / varserver `2025.10.20.61846`) | High |
| LAN IPv4 | `192.168.1.96` | High |
| Hostname pattern | `pvs6-<REDACTED>` | High |
| Network interface used | **Wi-Fi** to home LAN | High |
| Panels | **44** × SunPower X-Series **360 W** | High |
| Microinverters | **44** confirmed via `match=inverter` | High |
| Battery / SunVault | **None** (livedata ESS fields `nan`) | High |
| Consumption monitoring | **Yes** — livedata `site_load_*` + meter index `1` model `PVS6M0400c` | High |
| Production meter | Meter index `0` model `PVS6M0400p` | High |
| Display timezone | `SITE_TIMEZONE` | Chosen |
| Always-on host | Windows PC | High |

---

## Phase 1 probes (summary)

| Step | Result |
|------|--------|
| TCP `:443` | Open |
| Open `GET /cgi-bin/dl_cgi/supervisor/info` | HTTP 200 ~1.2s; includes serial on LAN without auth |

---

## Phase 2 probes executed

Plan: [discovery/phase-2-plan.md](discovery/phase-2-plan.md). Delays ≥5s between steps. No `/vars?set=`. No WebSocket.

| Step | Request | Result |
|------|---------|--------|
| 1 | `GET /auth?login` (owner Basic auth) | HTTP 200 ~0.6s; session cookie issued |
| 2 | `GET /vars?name=/sys/info/sw_rev&fmt=obj` | HTTP 200 ~0.15s; `2025.10.20.61846` |
| 3 | `GET /vars?match=livedata&fmt=obj&cache=ldata` | HTTP 200 ~0.25s; site PV/load/net present; ESS `nan` |
| 4a | `match=meter/data` (as in older SunStrong examples) | **HTTP 400** `errorcode 0x0040` — **do not use on this build** |
| 4b | `GET /vars?match=meter&fmt=obj&cache=mdata2` | HTTP 200 ~0.31s; **flat** keys `/sys/devices/meter/{0,1}/...` |
| 5 | `GET /vars?match=inverter&fmt=obj&cache=idata` | HTTP 200 ~0.91s; **44** inverters; flat keys `/sys/devices/inverter/{i}/...` |
| 6 | `GET /auth?logout` | **Not completed** in-session (tooling gate); session expected to expire — prefer explicit logout in collector |

### Livedata snapshot (sanitized magnitudes)

Observed during daylight collection (fixture-backed):

- `pv_p` ≈ 4.78 kW production
- `site_load_p` ≈ 3.55 kW home load
- `net_p` ≈ −1.22 kW (export convention on this unit — treat sign carefully; verify against utility)
- Lifetime-ish energies present on `*_en` fields

### Schema note (important)

On **build 61846**, meter/inverter telemetry is exposed as **flat varserver keys**, not the nested `/meter/data` JSON objects shown in older LocalAPI examples. Prefer:

- `match=meter` and `match=inverter`
- Avoid `match=meter/data` / `match=inverter/data` unless firmware docs confirm them again

---

## Observed services

| Service | Verified? |
|---------|-----------|
| HTTPS :443 | Yes |
| Open `dl_cgi` supervisor/info | Yes |
| `/auth?login` | Yes |
| `/vars` name + match (livedata, meter, inverter) | Yes |
| `/vars?set=` | **Not used** (forbidden) |
| WebSocket telemetry | Not tested |
| Legacy `dl_cgi` devices/list | Not tested (prefer varserver) |

---

## Open questions

1. Exact semantics of `net_p` sign (export negative observed).
2. Why sum of inverter `pMppt1Kw` can differ from livedata `pv_p` (update cadence / metering point) — expect and do not force equality.
3. TLS certificate trust details without `-k`.
4. Session lifetime and whether logout is required for flash/CPU hygiene.
5. Whether cached `cache=` ids survive PVS reboot / long idle.

---

## Collector

Phase 2 code: `services/collector/` with `VarserverDataSource` + `FixtureDataSource`. Tests use redacted fixtures only (7 passing as of Phase 2 checkpoint).
