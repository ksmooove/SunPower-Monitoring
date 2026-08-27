# Deploy cloud API to the droplet

Replace the temporary `whoami` stub with the real cloud FastAPI image.

## On your PC (or any machine with the repo + Docker)

Build and save the image, then copy to the droplet — **or** clone the repo on the droplet and build there.

### Option A — build on the droplet (simplest)

```bash
# on droplet
cd /opt
git clone <your-repo-url> solar-monitor   # or scp/rsync the repo
# If private repo, use a deploy key or copy files with scp.

mkdir -p /opt/solar-cloud
cp -a /opt/solar-monitor/infrastructure/cloud/. /opt/solar-cloud/
# Preserve existing DB + TLS data if you already ran the stub stack:
# (data/, caddy/, .env should already exist under /opt/solar-cloud)

# Merge new env keys into /opt/solar-cloud/.env:
#   CLOUD_SYNC_TOKEN=<strong random>
#   API_AUTH_TOKEN=<phone bearer>
#   API_HOST=solar.blackmagicsoftware.net
#   ACME_EMAIL=...
#   DATABASE_URL=postgresql://solar:...@db:5432/solar_monitor_cloud

chmod -R a+rX /opt/solar-cloud/db/init
cd /opt/solar-cloud

# Point compose build context at the monorepo root:
# Edit docker-compose.yml build.context from ../.. to /opt/solar-monitor
# OR keep files as:
#   /opt/solar-monitor/infrastructure/cloud/docker-compose.yml
# and run compose from there with project dir.

cd /opt/solar-monitor/infrastructure/cloud
cp /opt/solar-cloud/.env .env   # if .env lives only under solar-cloud
docker compose build api
docker compose up -d
docker compose ps
curl -sS https://solar.blackmagicsoftware.net/health
```

Recommended layout:

```text
/opt/solar-monitor/          # git clone
/opt/solar-cloud/.env         # secrets only (or symlink)
/opt/solar-cloud/data/        # postgres volume (bind mount)
/opt/solar-cloud/caddy/       # certs
```

Adjust compose volume paths accordingly, or run:

```bash
cd /opt/solar-monitor/infrastructure/cloud
ln -sfn /opt/solar-cloud/data ./data
ln -sfn /opt/solar-cloud/caddy ./caddy
ln -sfn /opt/solar-cloud/.env ./.env
chmod -R a+rX db/init
docker compose build api
docker compose up -d
```

## On the home PC — enable sync

In gitignored `.env`:

```env
CLOUD_SYNC_URL=https://solar.blackmagicsoftware.net
CLOUD_SYNC_TOKEN=<same as droplet CLOUD_SYNC_TOKEN>
API_AUTH_TOKEN=<phone token; also set on droplet>
```

```powershell
cd c:\Users\tony\Projects\solar-monitor
docker compose --profile cloud-sync up -d --build cloud-sync
docker compose logs -f cloud-sync
```

Then verify:

```powershell
curl.exe -sS https://solar.blackmagicsoftware.net/health
curl.exe -sS -H "Authorization: Bearer YOUR_PHONE_TOKEN" https://solar.blackmagicsoftware.net/v1/current
```

## Android

Open `apps/android` in Android Studio. Default base URL is `https://solar.blackmagicsoftware.net`. Set the phone Bearer token in Settings to match droplet `API_AUTH_TOKEN`.
