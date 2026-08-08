# Simulate a TradingView alert hitting the local agent (no ngrok needed)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$secretLine = Select-String -Path .\CREDENTIALS.txt -Pattern '^WEBHOOK_SECRET=' | Select-Object -First 1
$secret = ($secretLine.Line -split '=',2)[1].Trim()
$body = @{
    action = "BUY"
    symbol = "MES"
    price  = 7745.25
    time   = (Get-Date).ToString("o")
} | ConvertTo-Json
Write-Host "POST http://127.0.0.1:8787/tv  (simulating TradingView)..."
try {
    $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8787/tv?secret=$secret" -ContentType "application/json" -Body $body
    Write-Host "OK:" ($r | ConvertTo-Json -Compress)
    Write-Host "Now open: scripts\Open-Paper-View.ps1"
} catch {
    Write-Host "FAILED. Is the agent running with webhook? Start scripts\Setup-TradingView.ps1 first."
    Write-Host $_
    exit 1
}
