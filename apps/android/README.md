# Solar Monitor — Android

Native **Kotlin + Jetpack Compose** app (not a browser). Talks to the public cloud API over HTTPS via Retrofit/OkHttp.

Default base URL: `https://solar.blackmagicsoftware.net`

## Prerequisites

- Android Studio (SDK 35) + JDK 17
- Cloud API deployed — see [docs/cloud-deploy.md](../../docs/cloud-deploy.md)
- Home `cloud-sync` running so snapshots exist
- Phone Bearer token = droplet `API_AUTH_TOKEN` (not `CLOUD_SYNC_TOKEN`)

## Signing (release)

Uses the same upload keystore as your other apps: `C:\dev\SIGNKEYS\upload-keystore.jks`.

```powershell
cd apps\android
Copy-Item key.properties.example key.properties
# Edit key.properties with storePassword / keyAlias / keyPassword
.\gradlew.bat :app:assembleRelease
```

Output: `app\build\outputs\apk\release\app-release.apk`

## Debug build

```powershell
.\gradlew.bat :app:assembleDebug
```

## Settings

| Field | Value |
|-------|--------|
| API base URL | `https://solar.blackmagicsoftware.net` |
| Bearer token | Same as droplet `API_AUTH_TOKEN` |
