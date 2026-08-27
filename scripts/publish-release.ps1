#Requires -Version 5.1
<#
.SYNOPSIS
  Publish a Solar Monitor GitHub Release with a locally signed APK.

.DESCRIPTION
  1. Builds a signed release APK using apps/android/key.properties (your keystore).
  2. Creates annotated tag vX.Y.Z (if missing) and pushes it (triggers GHCR image workflow).
  3. Creates or updates the GitHub Release and uploads the APK.

  Docker images are built in CI (.github/workflows/release.yml), not here.
  Keystore secrets never leave this machine.

.PARAMETER Version
  Semver without leading v, e.g. 1.0.0

.PARAMETER SkipBuild
  Reuse an existing APK at the default path instead of rebuilding.

.PARAMETER DryRun
  Print actions without tagging, pushing, or uploading.
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+')]
    [string]$Version,

    [switch]$SkipBuild,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Tag = "v$Version"
$AndroidDir = Join-Path $RepoRoot "apps\android"
$ApkSrc = Join-Path $AndroidDir "app\build\outputs\apk\release\app-release.apk"
$ApkReleaseName = "solar-monitor-$Version.apk"
$ApkStaged = Join-Path $RepoRoot "dist\$ApkReleaseName"
$KeyProps = Join-Path $AndroidDir "key.properties"

function Assert-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Write-DryRun([string]$Message) {
    Write-Host ('[dry-run] ' + $Message)
}

Assert-Command git
Assert-Command gh

Push-Location $RepoRoot
try {
    $status = git status --porcelain
    if ($status) {
        Write-Warning "Working tree has uncommitted changes. Tag will point at HEAD anyway."
        Write-Host $status
    }

    if (-not (Test-Path $KeyProps)) {
        throw "Missing $KeyProps - copy key.properties.example and fill in your keystore values."
    }

    if (-not $SkipBuild) {
        Write-Host "==> Building signed release APK ($Version)..."
        if (-not $env:JAVA_HOME) {
            $jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-*" -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                Select-Object -First 1
            if ($jdk) { $env:JAVA_HOME = $jdk.FullName }
        }
        Push-Location $AndroidDir
        try {
            if ($DryRun) {
                Write-DryRun 'would run: .\gradlew.bat :app:assembleRelease'
            }
            else {
                & .\gradlew.bat :app:assembleRelease
                if ($LASTEXITCODE -ne 0) { throw "assembleRelease failed (exit $LASTEXITCODE)" }
            }
        }
        finally {
            Pop-Location
        }
    }

    if (-not $DryRun -and -not (Test-Path $ApkSrc)) {
        throw "APK not found: $ApkSrc"
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot "dist") | Out-Null
    if (-not $DryRun) {
        Copy-Item $ApkSrc $ApkStaged -Force
        Write-Host "==> Staged $ApkStaged"
    }

    $tagExists = git rev-parse -q --verify "refs/tags/$Tag" 2>$null
    if (-not $tagExists) {
        Write-Host "==> Creating annotated tag $Tag"
        if ($DryRun) {
            Write-DryRun "git tag -a $Tag -m 'Solar Monitor $Tag'"
        }
        else {
            git tag -a $Tag -m "Solar Monitor $Tag"
        }
    }
    else {
        Write-Host "==> Tag $Tag already exists locally"
    }

    Write-Host "==> Pushing tag $Tag (starts GHCR image workflow)"
    if ($DryRun) {
        Write-DryRun "git push origin $Tag"
    }
    else {
        git push origin $Tag
        if ($LASTEXITCODE -ne 0) { throw "git push origin $Tag failed" }
    }

    Write-Host "==> Publishing GitHub Release with local APK"
    $notes = @"
## Solar Monitor $Tag

Signed Android APK attached from a local keystore build.

Docker images are published by GitHub Actions to GHCR (solar-monitor-*:$Version). Refresh this page after the Release workflow finishes for the image list.

See docs/releasing.md.
"@

    if ($DryRun) {
        Write-DryRun "gh release create/upload $Tag -> $ApkReleaseName"
        Write-Host $notes
        return
    }

    $releaseExists = $false
    gh release view $Tag 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $releaseExists = $true }

    if ($releaseExists) {
        Write-Host "Release $Tag exists - uploading APK (clobber if present)"
        gh release upload $Tag $ApkStaged --clobber
        if ($LASTEXITCODE -ne 0) { throw "gh release upload failed" }
    }
    else {
        gh release create $Tag $ApkStaged `
            --title "Solar Monitor $Tag" `
            --notes $notes `
            --verify-tag
        if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }
    }

    $url = gh release view $Tag --json url -q .url
    Write-Host ""
    Write-Host "Done."
    Write-Host "  Release: $url"
    Write-Host "  APK:     $ApkReleaseName"
    Write-Host "  Images:  watch Actions workflow 'Release' for GHCR push"
}
finally {
    Pop-Location
}
