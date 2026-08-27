# Phase 1 discovery plan — controlled, single-host

**Status:** Approved and **executed** 2026-07-13. Steps 1–2 succeeded; Step 3 skipped. Results summarized in [`docs/pvs6-discovery.md`](../pvs6-discovery.md). Raw body (contains serial) only in gitignored `docs/discovery/private/`.

**Goal:** Confirm HTTPS reachability and capture firmware/supervisor fields from a **documented open** endpoint—or learn that authentication is required—without stressing the device.

---

## Target

| Parameter | Value |
|-----------|--------|
| Target IP | `192.168.1.96` only |
| Ports | **443/tcp** only (HTTPS) |
| Protocols | HTTPS |
| DNS/mDNS scans | None |
| Subnet scan | **Forbidden** |

## Request types (allowlist)

Execute **one step at a time**. Stop and record results before the next.

| Step | Method | Path / action | Auth | Max attempts |
|------|--------|---------------|------|--------------|
| 0 | Passive | Confirm firmware 61846 already recorded | N/A | Done |
| 1 | TCP connect test optional | Connect to `192.168.1.96:443` with short timeout | None | 1 |
| 2 | `GET` | Documented open legacy path: `/cgi-bin/dl_cgi/supervisor/info` (or SunStrong-documented equivalent open supervisor info) | None | 1 |
| 3 | Only if Step 2 fails with clear routing error | `GET` `/cgi-bin/dl_cgi/communication/interfaces` | None | 1 |

**Not in Phase 1:** `/auth?login`, `/vars`, device list, WebSocket, POST/PUT, path fuzzing, port lists beyond 443.

## Rate and concurrency

| Limit | Value |
|-------|--------|
| Concurrency | **1** |
| Delay between steps | Operator-driven (minutes apart is fine) |
| Maximum requests this phase | **≤ 3** total |
| Timeout | **15 seconds** connect/read |
| Retries | **0** (manual retry only after reviewing failure) |

## Stop conditions

Stop immediately if:

- Connection timeout or reset repeats
- PVS becomes unreachable from the phone app
- Unusual LED behavior or owner concern
- HTTP 5xx storms (even one 5xx → pause and reassess)
- Any response suggests we hit a write or destructive path (should not happen on allowlist)

## Logging and redaction

- Save status code, timing, and **redacted** body excerpts under `docs/discovery/private/` (gitignored) or local notes.
- Commit only sanitized summaries to `docs/pvs6-discovery.md`.
- Redact serials, MACs, tokens, cookies, emails, GPS.

## Adverse-effect observation

Before Step 1 and after each step:

1. Can the official monitoring app still open the system?
2. Any change in PVS LED pattern?
3. Router still shows the host lease?

## How results will be used

- Confirm TLS and open-endpoint behavior.
- Decide Phase 2 authenticated varserver probe plan (separate written plan).
- Never escalate to systematic endpoint discovery without a new allowlist.

## Operator approval

- [x] Owner approves this Phase 1 plan
- [x] Commands will be run only from a machine on the home LAN
- [x] Results will be sanitized before commit

---

## Candidate commands (for copy-paste after approval)

Run from **PowerShell on the Windows PC on the same LAN**. Expected: TLS connect; JSON or XML-like body, or HTTP 401/403 still useful.

### Step 1 — TCP reachability (optional)

```powershell
Test-NetConnection -ComputerName 192.168.1.96 -Port 443
```

Expected: `TcpTestSucceeded : True`. If False, stop and check Wi-Fi/AP isolation.

### Step 2 — one open supervisor info GET

```powershell
curl.exe -sk --connect-timeout 15 --max-time 15 "https://192.168.1.96/cgi-bin/dl_cgi/supervisor/info"
```

Expected (examples): JSON with supervisor/firmware fields; or an auth error; or HTML error. **Do not retry in a loop.** Record status with:

```powershell
curl.exe -sk -o supervisor-info.redact-me.json -w "http_code=%{http_code} time=%{time_total}\n" --connect-timeout 15 --max-time 15 "https://192.168.1.96/cgi-bin/dl_cgi/supervisor/info"
```

Store the file outside git or under a gitignored folder; paste only redacted fields into `docs/pvs6-discovery.md`.
