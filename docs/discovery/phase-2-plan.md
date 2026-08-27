# Phase 2 discovery plan — authenticated varserver (read-only)

**Status:** Executed 2026-07-13 (login, sw_rev, livedata, meter, inverter). Logout step deferred. Results in [`docs/pvs6-discovery.md`](../pvs6-discovery.md).

**Goal:** Confirm owner login and capture representative **read-only** varserver payloads (livedata, meters, inverters) for fixture development. No configuration writes. No WebSocket enable. No repeated polling.

---

## Target

| Parameter | Value |
|-----------|--------|
| Target IP | `192.168.1.96` only |
| Port | **443** HTTPS |
| Auth | Documented `ssm_owner` + last 5 chars of PVS serial (from local secret / prior private capture) |
| Writes | **Forbidden** (`/vars?set=` not allowed) |

## Allowlisted steps (one at a time)

| Step | Request | Purpose |
|------|---------|---------|
| 1 | `GET /auth?login` with Basic auth; store session cookie | Session |
| 2 | `GET /vars?name=/sys/info/sw_rev&fmt=obj` | Small authenticated read (no MAC) |
| 3 | `GET /vars?match=livedata&fmt=obj&cache=ldata` | Site live power + energy |
| 4 | `GET /vars?match=meter&fmt=obj&cache=mdata` (fallback if `meter/data` 400s) | Production/consumption meters |
| 5 | `GET /vars?match=inverter&fmt=obj&cache=idata` (not `inverter/data` on 61846) | Per-microinverter (expect ~44) |
| 6 | `GET /auth?logout` | Clean session |

**Not in this plan:** device-list `dl_cgi`, WebSocket, `set=`, path enumeration, retries in a loop, poll intervals.

## Limits

| Limit | Value |
|-------|--------|
| Concurrency | 1 |
| Delay between steps | ≥ 5 seconds |
| Timeout | 30 s (60 s allowed only for inverter match if needed) |
| Max requests | 6 |
| Retries | 0 automatic |

## Stop conditions

Same as Phase 1: timeouts, 5xx, app connectivity loss, owner concern, unexpected write semantics.

## Logging / redaction

- Raw responses → `docs/discovery/private/` (gitignored)
- Redacted fixtures → `fixtures/pvs6/*.json` (serials, MACs, session tokens scrubbed)
- Never commit cookies.txt

## Adverse-effect observation

After each step: note HTTP status and latency; stop if the PVS becomes unresponsive.
