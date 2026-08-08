$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "First-time setup..."
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install -e .
    if (-not (Test-Path .env)) { Copy-Item .env.example .env }
} else {
    .\.venv\Scripts\Activate.ps1
}

Write-Host "`n=== SWEEP RETEST AGENT (your TradingView logic) ===`n"
Write-Host "Uses live Yahoo bars for MES/MNQ. dry_run=true until you connect IBKR."
Write-Host "Add --webhook to accept TradingView alerts on port 8787.`n"

python -m agent.sweep_main --once --skip-session-check @args
python -m agent.tools.report --limit 15
