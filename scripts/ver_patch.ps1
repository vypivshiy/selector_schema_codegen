<# 
.SYNOPSIS
    Bump patch version (PowerShell equivalent of ver_patch.sh).
#>
$ErrorActionPreference = "Stop"

Write-Host "uv version --bump patch" -ForegroundColor Cyan
uv version --bump patch
