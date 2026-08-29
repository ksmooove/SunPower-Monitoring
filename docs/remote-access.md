# Remote access for mobile clients

Phones should talk to a **public HTTPS read API** on a cloud droplet that receives a **read-only sync** from home — not to the PVS, and not necessarily to the home PC.

## Preferred path (DigitalOcean)

1. Provision Ubuntu with [cloud-droplet-setup.md](./cloud-droplet-setup.md).
2. Sync a read-only slice from the home TimescaleDB (collector remains on the LAN).
3. Android / iOS use `https://<API_HOST>` + `Authorization: Bearer <API_AUTH_TOKEN>`.

Home stack stays source of truth. Cloud holds latest snapshot + history rollups for mobile.

## Optional: Tailscale to the home API

Tailscale Personal is free for typical home use and can still reach `http://<home>:8000` for admin or LAN-style debugging. It is **not required** for the DO mobile path.

If you use Tailscale:

1. Install on the Docker host and phone (same tailnet).
2. Hit `http://<host-magicdns-or-100.x>:8000/health`.
3. Prefer a strong `API_AUTH_TOKEN` in gitignored `.env`.

**Do not** port-forward home `8000`/`5432` to the public internet. **Do not** expose the PVS.

## OpenAPI contract

Canonical export: [openapi.json](./api/openapi.json) (refresh from a running API with `GET /openapi.json`).

### Stable mobile subset

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | No auth required |
| GET | `/v1/current` | Live livedata + inverters |
| GET | `/v1/day-summary` | Calendar-day energy in the configured `SITE_TIMEZONE` |
| GET | `/v1/playback?hours=` | Heatmap scrubber frames |
| GET | `/v1/history?...` | Time series |
| GET | `/v1/devices` | Device list + layout |
| PATCH | `/v1/devices/{id}/layout` | Optional; may stay home-only |

**Sign convention:** `net_power_kw` &lt; 0 ≈ export to grid; &gt; 0 ≈ import.

Collector poll interval remains **300s**; clients may poll every 15–30s for UI freshness.

## Clients

| Client | Path |
|--------|------|
| PWA (home LAN) | `apps/web` |
| Android (Kotlin) | `apps/android` → cloud HTTPS |
| iOS (future) | SwiftUI + same OpenAPI → cloud HTTPS |

Portrait power-flow art for mobile UI: `apps/web/public/images/power-flow-scene-portrait.jpg`.
