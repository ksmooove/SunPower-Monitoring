# Security Policy

## Scope

This repository is for **authorized local monitoring** of equipment the owner installs and operates at their home. It must not be used to access third-party systems, bypass authentication, or attack any network.

## Hard rules

1. **PVS6 only** — Interact solely with the PVS host the operator explicitly configures. Do not scan subnets or other hosts.
2. **Read-only by default** — Do not change PVS configuration, firmware, filesystem contents, or reboot the device unless the operator explicitly authorizes a documented, reviewed change.
3. **No exploitation** — No vulnerability scanning with exploit scripts, fuzzing, credential brute force, malformed payloads, or DoS testing.
4. **Rate limits** — Use strict timeouts, single concurrency by default, exponential backoff with jitter, and circuit breakers. Default poll interval is **300 seconds** unless evidence and operator approval justify a change.
5. **Secrets** — Never commit passwords, session cookies, tokens, private keys, full serial numbers, MAC addresses, or unredacted captures. Use `.env` (gitignored) and redacted fixtures only.
6. **No cloud exfiltration** — Do not upload captures, credentials, serials, or proprietary app packages to third-party services.
7. **Mediation** — Client apps talk to this project’s API only, never directly to the PVS6.
8. **Remote access** — Do not expose the PVS6 or this stack to the public internet via simple port forwarding. Prefer VPN (e.g. Tailscale/WireGuard) or an authenticated reverse proxy. A public VPS **cannot** reach a home PVS on Wi-Fi without a private tunnel; plan for collector-on-LAN first.

## Owner authentication (documented by SunStrong)

On firmware build ≥ 61840, local APIs use owner credentials documented by SunStrong Management (`ssm_owner` + last five characters of the PVS serial). Treat that password as a **secret**. Derive it locally; never commit it.

## LAN exposure note (observed)

On this site, the documented open `GET /cgi-bin/dl_cgi/supervisor/info` endpoint returns supervisor metadata including the device serial **without authentication**. Anyone on the LAN who can reach the PVS may learn that identifier. Keep the PVS off the public internet; do not commit raw responses.

## Reporting issues

If you discover a safety issue in this project’s collector (e.g. accidental write path, unbounded polling), open a private note with the operator and stop using the unsafe path immediately.
