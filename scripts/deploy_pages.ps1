<#
.SYNOPSIS
    Build the Vite Web Playground (playground/dist) and publish it to the gh-pages branch.
.PARAMETER BuildOnly
    Build playground/dist without modifying or pushing the gh-pages branch.
.PARAMETER NoPush
    Commit the built playground/dist artifact to the local gh-pages branch without pushing to origin.
#>
param(
    [switch]$BuildOnly,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

Write-Host "1/2 Installing dependencies & building Web Playground into playground/dist..." -ForegroundColor Cyan
npm --prefix playground install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix playground run build -- --emptyOutDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

New-Item -ItemType File -Path "playground/dist/.nojekyll" -Force | Out-Null

if ($BuildOnly) {
    Write-Host "Build complete (playground/dist/). Skipping gh-pages branch update (-BuildOnly)." -ForegroundColor Green
    exit 0
}

if ($NoPush) {
    Write-Host "2/2 Updating local gh-pages branch from playground/dist (without pushing)..." -ForegroundColor Cyan
    uv run --with ghp-import ghp-import -n -f playground/dist
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "2/2 Publishing playground/dist to gh-pages branch..." -ForegroundColor Cyan
    uv run --with ghp-import ghp-import -n -p -f playground/dist
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
