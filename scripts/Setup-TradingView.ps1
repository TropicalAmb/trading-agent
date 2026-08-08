# One-time / daily helper: start agent webhook + print TradingView alert settings
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    Write-Host "Run scripts\Start-Agent.ps1 once first to install."
    exit 1
}
.\.venv\Scripts\Activate.ps1
if (Test-Path .\CREDENTIALS.txt) { Copy-Item .\CREDENTIALS.txt .\.env -Force }

# Read secret
$secretLine = Select-String -Path .\CREDENTIALS.txt -Pattern '^WEBHOOK_SECRET=' | Select-Object -First 1
$secret = ($secretLine.Line -split '=',2)[1].Trim()
if (-not $secret -or $secret -like 'change-me*') {
    $secret = -join ((48..57)+(97..102) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    (Get-Content .\CREDENTIALS.txt) -replace 'WEBHOOK_SECRET=.*', "WEBHOOK_SECRET=$secret" | Set-Content .\CREDENTIALS.txt -Encoding utf8
    Copy-Item .\CREDENTIALS.txt .\.env -Force
}

Write-Host ""
Write-Host "======================================================"
Write-Host "  TRADINGVIEW → AGENT (signals IN)"
Write-Host "======================================================"
Write-Host ""
Write-Host "IMPORTANT: Bot orders will NOT appear in TradingView's"
Write-Host "Paper Trading panel. Check this instead every day:"
Write-Host "  data\paper_trading_view.html"
Write-Host "  (or run scripts\Open-Paper-View.ps1)"
Write-Host ""
Write-Host "1) Keep THIS agent window open."
Write-Host "2) Install ngrok if needed: https://ngrok.com/download"
Write-Host "3) In a SECOND PowerShell window run:"
Write-Host "     ngrok http 8787"
Write-Host "4) Copy the https://xxxx.ngrok-free.app URL"
Write-Host "5) In TradingView → Alert → Notifications → Webhook URL:"
Write-Host ""
Write-Host "   https://YOUR-NGROK-HOST/tv?secret=$secret"
Write-Host ""
Write-Host "6) Alert message (JSON):"
Write-Host ""
Write-Host '   {"action":"BUY","symbol":"MES","price":{{close}},"time":"{{timenow}}"}'
Write-Host ""
Write-Host "   or SELL. You need a TradingView plan that allows webhooks."
Write-Host "======================================================"
Write-Host ""

# Open paper view
python -c "from agent.paper.blotter import PaperBlotter; PaperBlotter().render_html()"
Start-Process (Join-Path (Get-Location) "data\paper_trading_view.html")

$env:USE_MOCK_BROKER = "true"
$env:WEBHOOK_SECRET = $secret
Write-Host "Starting agent in TV-alerts + autonomous mode..."
Write-Host "Local test (after start): another window can run Test-TradingView-Webhook.ps1"
Write-Host ""
python -m agent.live_main --mock --skip-session-check --webhook
