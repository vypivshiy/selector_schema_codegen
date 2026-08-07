<# 
.SYNOPSIS
    Format and auto-fix lint issues for source and tests (PowerShell equivalent of fix.sh).
#>
$ErrorActionPreference = "Stop"

$SourceFiles = "ssc_codegen"
$TestFiles = "tests"

Write-Host "ruff format $SourceFiles" -ForegroundColor Cyan
uv run ruff format $SourceFiles

Write-Host "ruff check $SourceFiles --fix" -ForegroundColor Cyan
uv run ruff check $SourceFiles --fix

Write-Host "ruff format $TestFiles" -ForegroundColor Cyan
uv run ruff format $TestFiles

Write-Host "ruff check $TestFiles --fix" -ForegroundColor Cyan
uv run ruff check $TestFiles --fix
