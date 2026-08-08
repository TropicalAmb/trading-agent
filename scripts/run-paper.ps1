$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "Run .\scripts\run-demo.ps1 once first for setup."
    exit 1
}
.\.venv\Scripts\Activate.ps1

Write-Host "`n=== PAPER RUN (needs IB Gateway on port 4002) ===`n"
Write-Host "Gateway must be open and logged into PAPER account."
Write-Host "dry_run is controlled in config\settings.yaml`n"
python -m agent.main --once --skip-session-check @args
python -m agent.tools.report --limit 20
