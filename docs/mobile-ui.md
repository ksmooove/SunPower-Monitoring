# Mobile UI

Phase 4 PWA (`apps/web`) — phone-first dashboard against the local API.

## Screens

1. **Live power** — solar / home / grid from `/v1/current`
2. **Day chart** — SVG chart from `/v1/history` (24h / 48h / 7d)
3. **Panel heatmap** — 44 inverters, blue→amber→cream scale (not red/green only)
4. **Editable layout** — `PATCH /v1/devices/{id}/layout` for row/col/name
5. **Health + freshness** — `/health`, offline cache of last current payload
6. **CSV export** — download link to `/v1/export.csv`

## Theme

- Fonts: Fraunces (display) + Manrope (body)
- Light/dark toggle (persisted)
- Warm solar amber on slate — not purple-default

## Access

- Docker: http://127.0.0.1:3080 (nginx proxies `/api` → API)
- Dev: `npm run dev` in `apps/web` → http://127.0.0.1:5173
