# Polling and hardware safety policy

## Principles

The PVS6 is fragile embedded equipment. Treat every request as a cost to CPU, flash, and stability. Prefer published community and SunStrong guidance over aggressive polling.

## Defaults (must hold unless an ADR changes them)

| Parameter | Default | Notes |
|-----------|---------|--------|
| Poll interval | **300 s** | Community evidence: inverter vars often refresh ~5 min; faster HTTP polling correlates with instability |
| Concurrency | **1** | No parallel PVS requests |
| Request timeout | **30 s** (up to 120 s only for known-slow documented calls) | Fail closed |
| Methods | **GET** (and documented auth login) only | No PUT/POST that mutate config/firmware |
| Writes to `/vars?set=` | **Forbidden** without explicit operator approval + ADR | Includes enabling telemetry WebSocket |
| Max failures before circuit open | **3** | Then cool-down ≥ 900 s |
| Backoff | Exponential + jitter | Cap reasonably (e.g. 15–30 min) |
| Target host | Single configured `PVS_HOST` | No subnet scans |

## Allowed request classes

1. **Documented open read endpoints** (Phase 1 discovery) — rare, manual or one-shot.
2. **Authenticated varserver reads** (`/vars` with name/cache; occasional `match=` to build a cache) — Phase 2+.
3. **Authenticated legacy reads** only when varserver cannot supply a needed field — sparse.

## Forbidden without written approval

- Port or path brute force beyond an allowlisted discovery plan
- Credential guessing
- Firmware/config changes, reboot, filesystem writes
- High-frequency polling (&lt; 60 s) or overlapping requests
- Malformed/large payloads, fuzzers, exploit scripts
- Contacting SunPower/SunStrong cloud except via normal user apps the owner already uses
- Uploading captures/serials/tokens to third parties

## Observing adverse effects

Before and during any active discovery or collection:

- Note PVS LED behavior and whether monitoring from the official app still works.
- Prefer one diagnostic step at a time; stop immediately on repeated errors, timeouts storms, or app/connectivity loss.
- Log request timing and HTTP status with **redaction** (no cookies, passwords, full serials).

## Cache discipline (varserver)

SunStrong docs recommend caching match queries and reusing `cache=` ids rather than repeating expensive match scans. Prefer:

1. One-time (or rare) `match=` to create a cache.
2. Steady-state polls using `cache=<id>&fmt=obj` at ≥ 300 s.

## Phase gate

No automated collector polling until:

1. This policy is accepted (it is, for Phase 0).
2. Phase 1 discovery plan is written and operator-approved.
3. Firmware and reachability are recorded in `docs/pvs6-discovery.md`.
