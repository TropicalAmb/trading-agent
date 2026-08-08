# Your daily paper trading view (replaces TradingView Paper Trading for the bot)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\Activate.ps1
python -c "from agent.paper.blotter import PaperBlotter; PaperBlotter().render_html(); print('ok')"
$path = Join-Path (Get-Location) "data\paper_trading_view.html"
Start-Process $path
Write-Host "Opened: $path"
Write-Host "Refresh happens automatically every 15 seconds while the file updates."
