# Redacted PVS6 fixtures

Sanitized JSON captures for parser and collector tests. Generated from private
discovery responses via `scripts/redact_fixtures.py`.

| File | Contents |
|------|----------|
| `supervisor-info.json` | Open `dl_cgi` supervisor info |
| `vars-sw-rev.json` | `/sys/info/sw_rev` |
| `vars-livedata.json` | `match=livedata` |
| `vars-meter.json` | `match=meter` (flat paths on build 61846) |
| `vars-inverter.json` | `match=inverter` (44 microinverters) |

**Do not** commit files under `docs/discovery/private/` or `unredacted/`.
