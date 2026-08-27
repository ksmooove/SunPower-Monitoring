# Remaining setup — command by command

You already started **home** `cloud-sync`. That will keep failing until the droplet runs the **real cloud API** (not `whoami`). Do the droplet first, then verify sync, then Android.

Replace secrets in angle brackets. Your FQDN: `solar.blackmagicsoftware.net`.

---

## A. Copy the repo to the droplet (from your Windows PC)

PowerShell on the PC. **Important:** paths must end up as
`/opt/solar-monitor/apps/cloud-api` and `/opt/solar-monitor/infrastructure/...`
(not `/opt/solar-monitor/cloud-api`).

### Preferred: tar (preserves folder layout)

```powershell
cd c:\Users\tony\Projects
tar -czf solar-monitor-cloud.tgz -C solar-monitor apps/cloud-api infrastructure
scp solar-monitor-cloud.tgz root@solar.blackmagicsoftware.net:/tmp/
ssh root@solar.blackmagicsoftware.net "rm -rf /opt/solar-monitor && mkdir -p /opt/solar-monitor && tar -xzf /tmp/solar-monitor-cloud.tgz -C /opt/solar-monitor && rm /tmp/solar-monitor-cloud.tgz && ls -la /opt/solar-monitor && ls -la /opt/solar-monitor/apps/cloud-api | head"
```

### Alternate: scp (must target `apps/`)

```powershell
cd c:\Users\tony\Projects\solar-monitor
ssh root@solar.blackmagicsoftware.net "mkdir -p /opt/solar-monitor/apps"
scp -r apps\cloud-api root@solar.blackmagicsoftware.net:/opt/solar-monitor/apps/
scp -r infrastructure root@solar.blackmagicsoftware.net:/opt/solar-monitor/
```

### Verify on the droplet (do this before build)

```bash
ssh root@solar.blackmagicsoftware.net
ls -la /opt/solar-monitor/apps/cloud-api/pyproject.toml
ls -la /opt/solar-monitor/infrastructure/docker/Dockerfile.cloud-api
```

Both files must exist. If you previously copied wrong and have `/opt/solar-monitor/cloud-api` instead:

```bash
mkdir -p /opt/solar-monitor/apps
mv /opt/solar-monitor/cloud-api /opt/solar-monitor/apps/cloud-api
```

---

## B. On the droplet — wire compose to existing data + TLS

Confirm `.env` has both tokens (add if missing):

```bash
grep -E 'API_AUTH_TOKEN|CLOUD_SYNC_TOKEN|API_HOST|DATABASE_URL|POSTGRES_' /opt/solar-cloud/.env
```

You need at least:

```env
API_HOST=solar.blackmagicsoftware.net
ACME_EMAIL=...
POSTGRES_USER=solar
POSTGRES_PASSWORD=...
POSTGRES_DB=solar_monitor_cloud
DATABASE_URL=postgresql://solar:...@db:5432/solar_monitor_cloud
API_AUTH_TOKEN=...          # phone
CLOUD_SYNC_TOKEN=...        # home syncer (same as home .env)
```

Stop the old whoami stack (keeps volumes/files) if still running:

```bash
cd /opt/solar-cloud
docker compose down
```

Point the new compose at your existing data/certs/env:

```bash
cd /opt/solar-monitor/infrastructure/cloud
ln -sfn /opt/solar-cloud/data ./data
ln -sfn /opt/solar-cloud/caddy ./caddy
ln -sfn /opt/solar-cloud/.env ./.env
chmod -R a+rX ./db/init
```

Update Caddy to proxy port **8000** (real API):

```bash
cat > /opt/solar-monitor/infrastructure/cloud/Caddyfile <<'EOF'
{
        email {$ACME_EMAIL}
}

{$API_HOST} {
        encode gzip
        reverse_proxy api:8000
}
EOF
```

### Build and start

Compose build context is `/opt/solar-monitor` (`context: ../..` from `infrastructure/cloud`). That directory **must** contain `apps/cloud-api`.

```bash
cd /opt/solar-monitor/infrastructure/cloud

# Sanity check (must print the pyproject path)
test -f /opt/solar-monitor/apps/cloud-api/pyproject.toml && echo "cloud-api OK" || echo "MISSING apps/cloud-api — fix section A"

docker compose build api
docker compose up -d
docker compose ps
docker compose logs api --tail=50
```

If build fails with `"/apps/cloud-api": not found`, section A layout is wrong — fix paths and rebuild.

Expect `db` healthy, `api` healthy, `caddy` running.

### If API is unhealthy: Timescale version mismatch

Symptom in `docker compose logs api`:

`could not access file "$libdir/timescaledb-2.28.2": No such file or directory`

Cause: data dir was created with `latest-pg16` (Timescale ~2.28), but compose briefly pinned `2.19.3-pg16`.

**Fix (keep existing data)** — use `latest-pg16` for `db`:

```bash
cd /opt/solar-monitor/infrastructure/cloud
# Ensure docker-compose.yml db image is:
#   image: timescale/timescaledb:latest-pg16
sed -i 's|image: timescale/timescaledb:2.19.3-pg16|image: timescale/timescaledb:latest-pg16|' docker-compose.yml
grep -n 'image: timescale' docker-compose.yml
docker compose up -d
docker compose ps
docker compose logs api --tail=30
curl -sS https://solar.blackmagicsoftware.net/health
```

**Alternate (wipe empty cloud DB)** — only if you prefer pinning an older tag and have no synced data yet:

```bash
docker compose down
rm -rf /opt/solar-cloud/data/db
mkdir -p /opt/solar-cloud/data/db
# set image to your chosen pin, then:
docker compose up -d
```

Smoke test on the droplet:

```bash
curl -sS https://solar.blackmagicsoftware.net/health
```

You want JSON like `"service":"solar-cloud-api"`, not whoami text.

---

## C. On the home PC — confirm sync

```powershell
cd c:\Users\tony\Projects\solar-monitor

# Restart sync so it hits the real /v1/ingest
docker compose --profile cloud-sync up -d --build cloud-sync
docker compose logs cloud-sync --tail=80
```

Look for a line like `synced to https://solar.blackmagicsoftware.net/v1/ingest`.

### If sync fails: `Object of type UUID is not JSON serializable`

Rebuild after pulling the fix (UUID → string in the syncer):

```powershell
docker compose --profile cloud-sync up -d --build cloud-sync
docker compose logs cloud-sync --tail=40
```

If you see `404` / `403` / connection errors, fix tokens or redeploy API first.

Verify phone endpoints (use your **API_AUTH_TOKEN**, not the sync token):

```powershell
curl.exe -sS https://solar.blackmagicsoftware.net/health
curl.exe -sS -H "Authorization: Bearer YOUR_PHONE_API_AUTH_TOKEN" https://solar.blackmagicsoftware.net/v1/current
curl.exe -sS -H "Authorization: Bearer YOUR_PHONE_API_AUTH_TOKEN" https://solar.blackmagicsoftware.net/v1/day-summary
```

`/v1/current` may be `404` until the first successful sync; after sync it should return livedata JSON.

---

## D. Android (signed release APK)

Signing reuses `C:\dev\SIGNKEYS\upload-keystore.jks` (same upload key as your other apps).

### D1. Create local `key.properties` (once)

```powershell
cd c:\Users\tony\Projects\solar-monitor\apps\android
Copy-Item key.properties.example key.properties
notepad key.properties
```

Set:

```properties
storeFile=C:/dev/SIGNKEYS/upload-keystore.jks
storePassword=<your store password>
keyAlias=upload
keyPassword=<your key password>
```

(`keyAlias` is usually `upload` for Play upload keystores — change if yours differs.)

`key.properties` is gitignored. Never commit passwords.

### D2. Build signed release

```powershell
cd c:\Users\tony\Projects\solar-monitor\apps\android
.\gradlew.bat :app:assembleRelease
```

Signed APK:

`app\build\outputs\apk\release\app-release.apk`

Install on the phone:

```powershell
adb install -r app\build\outputs\apk\release\app-release.apk
```

Or copy the APK to the phone and open it.

### D3. App settings

| Field | Value |
|-------|--------|
| API base URL | `https://solar.blackmagicsoftware.net` |
| Bearer token | Same as droplet / home `API_AUTH_TOKEN` |

Open **Live** → Refresh. You should see solar / home / grid and today’s totals.

Debug builds still work without signing: `.\gradlew.bat :app:assembleDebug`.

---

## Checklist

1. [ ] `/opt/solar-monitor/apps/cloud-api/pyproject.toml` exists on droplet
2. [ ] Droplet `curl /health` → `solar-cloud-api`
3. [ ] Home `cloud-sync` logs → successful ingest
4. [ ] `curl /v1/current` with phone token → JSON
5. [ ] Android app Live tab shows data

If anything fails, paste: `ls -la /opt/solar-monitor /opt/solar-monitor/apps`, `docker compose ps`, and `docker compose logs api --tail=50` from the droplet, plus `docker compose logs cloud-sync --tail=50` from home.
