$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install -e .
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
} else {
    .\.venv\Scripts\Activate.ps1
}

Write-Host "`n=== LIVE AGENT (research strategy: filtered ORB + VWAP) ==="
Write-Host "Broker backend: Tradovate/Topstep (see CONNECT_REAL.md)"
Write-Host "Default dry_run=true. Use --mock if credentials not set yet.`n"

python -m agent.live_main --mock --once --skip-session-check @args
python -m agent.tools.report --limit 15
