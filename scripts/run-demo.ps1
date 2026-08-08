$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "First-time setup: creating virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install -e .
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
} else {
    .\.venv\Scripts\Activate.ps1
}

Write-Host "`n=== DEMO RUN (fake broker, no real money) ===`n"
python -m agent.main --mock --once --skip-session-check
Write-Host "`n=== JOURNAL SUMMARY ===`n"
python -m agent.tools.report --limit 20
Write-Host "`nDone. Open data\decisions.csv to see details.`n"
