<#
.SYNOPSIS
    Build MkDocs documentation + Vite Web Playground and publish to gh-pages.
.PARAMETER BuildOnly
    Build site/ and site/playground/ without modifying or pushing the gh-pages branch.
.PARAMETER NoPush
    Commit the built site/ artifact to the local gh-pages branch without pushing to origin.
#>
param(
    [switch]$BuildOnly,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

Write-Host "1/3 Building MkDocs documentation into site/..." -ForegroundColor Cyan
uv run --group docs mkdocs build --clean --strict
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "2/3 Installing dependencies & building Web Playground into site/playground/..." -ForegroundColor Cyan
npm --prefix playground install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix playground run build -- --outDir ../site/playground --emptyOutDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($BuildOnly) {
    Write-Host "Build complete (site/ and site/playground/). Skipping gh-pages branch update (-BuildOnly)." -ForegroundColor Green
    exit 0
}

if ($NoPush) {
    Write-Host "3/3 Updating local gh-pages branch (without pushing)..." -ForegroundColor Cyan
    uv run --group docs ghp-import -n -f site
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "3/3 Publishing site/ to gh-pages branch..." -ForegroundColor Cyan
    uv run --group docs ghp-import -n -p -f site
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
