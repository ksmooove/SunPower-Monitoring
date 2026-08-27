# Cloud read replica — Ubuntu droplet setup (DigitalOcean)

Command-by-command runbook for a **clean Ubuntu** droplet that holds a **read-only slice** of Solar Monitor data for Android / future iOS.

Home stack stays the source of truth (collector → Timescale on your LAN). The droplet only receives synced data and serves a public HTTPS API. The PVS6 is **never** reachable from the internet.

**Assumptions**

- Ubuntu **24.04 LTS** x64 droplet
- You have SSH key auth to the droplet
- You own a DNS name (or will use the droplet IP temporarily; HTTPS needs a name)
- You will create the sync job and thin cloud API in a later coding step

Replace placeholders:

| Placeholder | Example |
|-------------|---------|
| `DROPLET_IP` | `203.0.113.10` |
| `API_HOST` | `solar-api.example.com` |
| `YOUR_EMAIL` | Let’s Encrypt registration email |

---

## 0. Create the droplet (DigitalOcean UI)

1. Create → Droplets → **Ubuntu 24.04 LTS**.
2. Size: 1 vCPU / 1 GB RAM is enough to start (2 GB if you keep long inverter history).
3. Region: closest to you.
4. Authentication: **SSH key** (disable password auth later).
5. Hostname e.g. `solar-cloud`.
6. Note the public IPv4 → `DROPLET_IP`.

Optional: assign a reserved IP / floating IP if you want a stable address.

Point DNS **A record** `API_HOST` → `DROPLET_IP` before the TLS step (or use HTTP-only briefly for smoke tests).

---

## 1. First login and baseline updates

From your PC:

```bash
ssh root@DROPLET_IP
```

On the droplet:

```bash
apt update && apt upgrade -y
timedatectl set-timezone America/Los_Angeles
hostnamectl set-hostname solar-cloud
```

Optional non-root admin user (recommended):

```bash
adduser tony
usermod -aG sudo tony
rsync --archive --chown=tony:tony /root/.ssh /home/tony/
```

Log out and back in as that user (with sudo), or continue as root for the rest of this guide.

---

## 2. Firewall (UFW)

```bash
apt install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status verbose
```

Do **not** open Postgres (`5432`) to the world.

---

## 3. Install Docker Engine + Compose plugin

```bash
apt install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

If you use a non-root user:

```bash
usermod -aG docker tony
# log out/in so the group applies
```

Verify:

```bash
docker --version
docker compose version
docker run --rm hello-world
```

---

## 4. App directory and secrets

```bash
mkdir -p /opt/solar-cloud/{data/db,caddy/data,caddy/config}
cd /opt/solar-cloud
```

Generate a strong API token (save it; Android/iOS will use it):

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
```

Create env file (mode 600):

```bash
umask 077
cat > /opt/solar-cloud/.env <<'EOF'
POSTGRES_USER=solar
POSTGRES_PASSWORD=CHANGE_ME_DB_PASSWORD
POSTGRES_DB=solar_monitor_cloud
DATABASE_URL=postgresql://solar:CHANGE_ME_DB_PASSWORD@db:5432/solar_monitor_cloud
API_AUTH_TOKEN=CHANGE_ME_API_TOKEN
API_HOST=solar-api.example.com
ACME_EMAIL=you@example.com
EOF
chmod 600 /opt/solar-cloud/.env
```

Edit real values:

```bash
nano /opt/solar-cloud/.env
```

---

## 5. Docker Compose stack (DB + API + Caddy)

This layout matches what we will wire in-repo later (`infrastructure/cloud/` or similar). For now, create the files on the droplet so the host is ready.

### 5.1 `docker-compose.yml`

```bash
cat > /opt/solar-cloud/docker-compose.yml <<'EOF'
services:
  db:
    image: timescale/timescaledb:latest-pg16
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - ./data/db:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      # Use pg_isready without env expansion quirks; start_period covers first init.
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-solar} -d $${POSTGRES_DB:-solar_monitor_cloud} || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 30
      start_period: 40s
    networks: [internal]

  api:
    # Placeholder until the cloud API image is built from this repo.
    # Temporary: keep the container definition; replace image after first cloud API commit.
    image: traefik/whoami:v1.10
    restart: unless-stopped
    environment:
      DATABASE_URL: ${DATABASE_URL}
      API_AUTH_TOKEN: ${API_AUTH_TOKEN}
    depends_on:
      db:
        condition: service_healthy
    networks: [internal]
    # No host ports — only Caddy reaches the API

  caddy:
    image: caddy:2.8-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    environment:
      API_HOST: ${API_HOST}
      ACME_EMAIL: ${ACME_EMAIL}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./caddy/data:/data
      - ./caddy/config:/config
    depends_on:
      - api
    networks: [internal, edge]

networks:
  internal:
    internal: true
  edge:
EOF
```

> Note: `api` uses a temporary `whoami` image so Compose and Caddy can be proven before we ship the real FastAPI cloud image. After the cloud API lands in git, you will change `api.image` (or `build:`) and re-deploy.

### 5.2 Minimal DB init (hypertables later)

```bash
mkdir -p /opt/solar-cloud/db/init
cat > /opt/solar-cloud/db/init/001_extensions.sql <<'EOF'
CREATE EXTENSION IF NOT EXISTS timescaledb;
EOF
# Postgres runs as a non-root user and must be able to list this mount:
chmod -R a+rX /opt/solar-cloud/db/init
```

### 5.3 Caddyfile (HTTPS reverse proxy)

```bash
cat > /opt/solar-cloud/Caddyfile <<'EOF'
{
        email {$ACME_EMAIL}
}

{$API_HOST} {
        encode gzip
        reverse_proxy api:80
}
EOF
```

When the real API listens on **8000**, change the last line to `reverse_proxy api:8000`.

---

## 6. Start the stack

```bash
cd /opt/solar-cloud
docker compose pull
docker compose up -d
docker compose ps
docker compose logs -f --tail=50
```

### If `db` is unhealthy

Inspect first (paste output if you need help):

```bash
cd /opt/solar-cloud
docker compose ps -a
docker compose logs db --tail=100
free -h
df -h /opt/solar-cloud/data
```

Common causes and fixes:

**0. Init dir not readable by Postgres** — classic after `umask 077`. Logs show  
`ls: can't open '/docker-entrypoint-initdb.d/': Permission denied`.

```bash
chmod -R a+rX /opt/solar-cloud/db/init
docker compose down
rm -rf /opt/solar-cloud/data/db && mkdir -p /opt/solar-cloud/data/db
docker compose up -d
```

**1. First boot still initializing** — wait ~60s, then:

```bash
docker compose up -d
```

**2. Bad/partial data dir from a failed first start** — reset local DB volume (destroys cloud DB data):

```bash
docker compose down
rm -rf /opt/solar-cloud/data/db
mkdir -p /opt/solar-cloud/data/db
docker compose up -d
```

**3. Password / `.env` interpolation** — avoid `$`, `` ` ``, `"`, and `\` in `POSTGRES_PASSWORD`. Prefer a long alphanumeric token.

**4. Init SQL failing** — temporarily move init aside, bring DB up, then add the extension by hand:

```bash
mv /opt/solar-cloud/db/init /opt/solar-cloud/db/init.bak
docker compose down
rm -rf /opt/solar-cloud/data/db && mkdir -p /opt/solar-cloud/data/db
docker compose up -d db
docker compose logs db --tail=50
# when healthy:
docker compose exec db psql -U solar -d solar_monitor_cloud -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
docker compose up -d
```

**5. Tiny droplet OOM** — Timescale likes ≥1 GB RAM. Check `free -h`; resize the droplet if memory is exhausted.

After updating `docker-compose.yml` on the droplet to match this doc (healthcheck `start_period`), re-copy the file or edit in place, then `docker compose up -d`.

Smoke tests from your PC (after DNS points at the droplet):

```bash
curl -sS https://API_HOST/
# Temporary whoami JSON/text is fine — proves TLS + proxy.
```

HTTP → HTTPS should redirect automatically via Caddy.

---

## 7. Postgres access (localhost / Docker network only)

```bash
cd /opt/solar-cloud
docker compose exec db psql -U solar -d solar_monitor_cloud -c '\dx'
```

Confirm Timescale extension is listed. No public bind of `5432`.

---

## 8. Sync identity (for the home exporter later)

Create a DB role used **only** by the home → cloud sync (not by phones):

```bash
docker compose exec -T db psql -U solar -d solar_monitor_cloud -v ON_ERROR_STOP=1 \
  -c "CREATE ROLE solar_sync LOGIN PASSWORD 'CHANGE_ME_SYNC_PASSWORD';" \
  -c "GRANT CONNECT ON DATABASE solar_monitor_cloud TO solar_sync;"
```

Or, if you prefer a here-doc, force non-TTY stdin with `-T`:

```bash
docker compose exec -T db psql -U solar -d solar_monitor_cloud <<'SQL'
CREATE ROLE solar_sync LOGIN PASSWORD 'CHANGE_ME_SYNC_PASSWORD';
GRANT CONNECT ON DATABASE solar_monitor_cloud TO solar_sync;
SQL
```

Store `CHANGE_ME_SYNC_PASSWORD` in the **home** `.env` (gitignored), never in the Android app.

Phones use **HTTPS + `API_AUTH_TOKEN` only** — never DB credentials.

---

## 9. Automatic updates (optional but recommended)

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

Rebuild/pull app images on your schedule (e.g. weekly):

```bash
cd /opt/solar-cloud
docker compose pull
docker compose up -d
docker image prune -f
```

---

## 10. What we will add in code next (not in this runbook)

Implemented in-repo — follow **[cloud-deploy.md](./cloud-deploy.md)** to:

1. Replace `whoami` with the **cloud FastAPI** image (`apps/cloud-api`).
2. Run **home → cloud sync** (`services/cloud-sync`, Compose profile `cloud-sync`).
3. Point the **Kotlin Android app** at `https://solar.blackmagicsoftware.net` with `API_AUTH_TOKEN`.

Suggested data slice (v1):

| Slice | Cadence | Notes |
|-------|---------|--------|
| Latest livedata snapshot | every sync cycle (~5 min) | Powers live UI |
| Calendar day summary | every cycle | Cheap |
| Site `pv_power_kw` history | last 48h by default | Charts |

---

## 11. Rollback / destroy

```bash
cd /opt/solar-cloud
docker compose down
# wipe DB volume only if you intend to reset:
# rm -rf /opt/solar-cloud/data/db
```

Destroy the droplet in DigitalOcean when done testing.

---

## 12. Security checklist

- [ ] SSH key only; password auth disabled (`PasswordAuthentication no` in `sshd_config`)
- [ ] UFW: 22/80/443 only
- [ ] Postgres not published to the host/public interface
- [ ] Strong `POSTGRES_PASSWORD`, `API_AUTH_TOKEN`, sync secret
- [ ] DNS + TLS on `API_HOST`
- [ ] No PVS credentials on the droplet
- [ ] Android stores token in encrypted prefs / Keystore (later)

---

## Quick reference

| Item | Value |
|------|--------|
| App dir | `/opt/solar-cloud` |
| Compose | `docker compose up -d` |
| Logs | `docker compose logs -f api caddy db` |
| Public URL | `https://API_HOST` |
| Phone auth | `Authorization: Bearer <API_AUTH_TOKEN>` |

When this droplet is up and `curl https://API_HOST/` works, tell me and we will implement the cloud API image + home sync job next, then point `apps/android` at `https://API_HOST`.
