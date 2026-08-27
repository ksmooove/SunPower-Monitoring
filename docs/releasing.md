# Publishing a release

A release is a **git tag** `vX.Y.Z` plus:

| Artifact | How |
|----------|-----|
| Docker images | GitHub Actions → GHCR (`ghcr.io/<owner>/solar-monitor-*`) |
| Signed Android APK | **Local only** (your upload keystore) → GitHub Release asset |

The keystore never goes into CI.

## Prerequisites

- `git` and [GitHub CLI](https://cli.github.com/) (`gh auth login`)
- JDK 17 + `apps/android/key.properties` (from `key.properties.example`)
- Push access to the GitHub repo; GHCR packages enabled for the org/user
- Clean-enough `main` (or release branch) at the commit you want to ship

## One-command local publish

From the repo root (PowerShell):

```powershell
# First time / full release
.\scripts\publish-release.ps1 -Version 1.0.0

# APK already built
.\scripts\publish-release.ps1 -Version 1.0.0 -SkipBuild

# Preview
.\scripts\publish-release.ps1 -Version 1.0.0 -DryRun
```

What it does:

1. Runs `assembleRelease` with your local keystore  
2. Copies APK to `dist/solar-monitor-1.0.0.apk`  
3. Creates annotated tag `v1.0.0` if needed and `git push origin v1.0.0`  
4. Creates the GitHub Release (or uploads the APK if CI already created it)

Pushing the tag starts [`.github/workflows/release.yml`](../.github/workflows/release.yml), which builds and pushes:

- `solar-monitor-api`
- `solar-monitor-web`
- `solar-monitor-collector`
- `solar-monitor-migrate`
- `solar-monitor-cloud-sync`
- `solar-monitor-cloud-api`

Each image is tagged `1.0.0`, `v1.0.0`, and `latest`.

## Manual APK-only upload

If the tag/release already exists and you only need to attach a new APK:

```powershell
cd apps\android
.\gradlew.bat :app:assembleRelease
cd ..\..
New-Item -ItemType Directory -Force dist | Out-Null
Copy-Item apps\android\app\build\outputs\apk\release\app-release.apk dist\solar-monitor-1.0.0.apk -Force
gh release upload v1.0.0 dist\solar-monitor-1.0.0.apk --clobber
```

## Pulling images after release

Replace `<owner>` with the lowercase GitHub user/org:

```bash
docker pull ghcr.io/<owner>/solar-monitor-api:1.0.0
docker pull ghcr.io/<owner>/solar-monitor-web:1.0.0
docker pull ghcr.io/<owner>/solar-monitor-collector:1.0.0
docker pull ghcr.io/<owner>/solar-monitor-cloud-api:1.0.0
```

Private GHCR packages need `docker login ghcr.io` with a PAT that has `read:packages`.

Day-to-day home/cloud deploys can keep using `docker compose build` from git; published images are for pinned, reproducible installs.

## What not to publish

- `.env`, tokens, Postgres passwords  
- `key.properties` / `.jks` keystore  
- Database dumps with personal telemetry (unless you intentionally redact)
