# Cloud replica (DigitalOcean)

Compose file for the droplet at `/opt/solar-cloud`. Full host bootstrap:
[docs/cloud-droplet-setup.md](../../docs/cloud-droplet-setup.md).

## Deploy / update from this repo

On the droplet (after cloning or copying files):

```bash
cd /opt/solar-cloud
# Ensure .env has POSTGRES_*, API_AUTH_TOKEN, CLOUD_SYNC_TOKEN, API_HOST, ACME_EMAIL

# If deploying from a git checkout of the monorepo:
cp -a /path/to/solar-monitor/infrastructure/cloud/* /opt/solar-cloud/
# keep existing data/ and .env

docker compose build api
docker compose up -d
docker compose ps
curl -sS https://$API_HOST/health
```

Caddy proxies to the cloud API on port **8000**.
