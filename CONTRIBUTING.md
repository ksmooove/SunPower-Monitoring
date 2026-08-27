# Contributing

This is a single-homeowner, production-quality personal project. Changes should stay small, reviewable, and hardware-safe.

## Working style

1. Inspect the repo and relevant docs before changing code.
2. Prefer the smallest useful next step; stop at phase checkpoints.
3. Record meaningful architectural decisions under `docs/adr/`.
4. Update documentation in the same change when behavior or safety policy shifts.
5. Never commit secrets, unredacted PVS payloads, or proprietary app packages.

## Development standards (target)

- Locked dependency versions
- Automated format/lint and type checks
- Unit tests + fixture-based parser tests (no real PVS required in CI)
- Docker Compose for local deployment
- Structured logging and health endpoints

## Pull requests / commits

- Explain *why*, not only *what*
- Call out any new PVS request paths and their rate limits
- Include verification steps that do not require live hardware when fixtures exist

## Safety review checklist

- [ ] Read-only against PVS (or explicit write ADR + operator approval)
- [ ] Timeouts, concurrency ≤ 1 unless justified
- [ ] Poll interval ≥ configured minimum (default 300s)
- [ ] Errors trigger backoff / circuit breaker
- [ ] Logs redact serials, MACs, tokens, cookies
