$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "Run .\scripts\run-demo.ps1 once first for setup."
    exit 1
}
.\.venv\Scripts\Activate.ps1

Write-Host "`n=== BACKTEST (historical simulation) ===`n"
python -m agent.tools.backtest @args
