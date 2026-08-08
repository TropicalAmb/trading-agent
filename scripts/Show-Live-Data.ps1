# Prove the agent can see real MES/MNQ prices (Yahoo) — no broker $1k needed
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
.\.venv\Scripts\Activate.ps1
Write-Host ""
Write-Host "Pulling LIVE market bars from Yahoo Finance (MES=F / MNQ=F)..."
Write-Host "This is what the strategy already uses. Mock only fakes ORDERS."
Write-Host ""
python -c @"
from agent.market.bars import log_market_data_status
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
log_market_data_status(['MES', 'MNQ'])
"@
