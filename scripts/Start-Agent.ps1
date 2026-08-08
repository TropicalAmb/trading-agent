# Daily launcher: real Yahoo bars + paper blotter + agent loop
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "First-time setup - installing (one time)..."
    python -m venv .venv
    & .\scripts\bootstrap.ps1
    $py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
}

if (Test-Path .\CREDENTIALS.txt) {
    Copy-Item .\CREDENTIALS.txt .\.env -Force
}

Write-Host ""
Write-Host "============================================"
Write-Host "  BOT RUNNING while this window stays open"
Write-Host "  Markets: MES + MNQ"
Write-Host "  Entries: anytime CME is open (pause ~5-6pm ET + weekend)"
Write-Host "  Paper View: Desktop -> Open Agent Paper View"
Write-Host "  Trade log CSV: data\trade_journal.csv"
Write-Host "  Red text is often normal INFO (look for ERROR)"
Write-Host "============================================"
Write-Host ""

& $py .\scripts\healthcheck.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Health check failed. Press any key to close."
    pause
    exit 1
}

$html = Join-Path (Get-Location) "data\paper_trading_view.html"
if (Test-Path $html) {
    Start-Process $html
}

$env:USE_MOCK_BROKER = "true"
Write-Host ""
Write-Host "Starting agent (Ctrl+C or close window to stop)..."
Write-Host "Paper mode only - no real money."
& $py -m agent.live_main --mock --webhook
Write-Host ""
Write-Host "Agent stopped."
pause
