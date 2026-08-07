<# 
.SYNOPSIS
    Format, lint, run tests, and type-check (PowerShell equivalent of check.sh).
#>
$ErrorActionPreference = "Stop"

$SourceFiles = "ssc_codegen"

Write-Host "ruff format $SourceFiles" -ForegroundColor Cyan
uv run ruff format $SourceFiles

Write-Host "ruff check $SourceFiles" -ForegroundColor Cyan
uv run ruff check $SourceFiles

Write-Host "pytest" -ForegroundColor Cyan
uv run pytest

Write-Host "mypy $SourceFiles" -ForegroundColor Cyan
uv run mypy $SourceFiles
