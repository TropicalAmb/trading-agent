# Install / refresh the independent 5-minute watchdog task.
# Task is HIDDEN and does NOT WakeToRun (no terminal flash / no wake-on-plug).
$ErrorActionPreference = "Continue"
$Root = "C:\Users\patri\trading-agent"
$Python = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $Python)) {
  $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
$Script = Join-Path $Root "scripts\watchdog_tick.py"
$TaskName = "TradingAgentWatchdog"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
  -MultipleInstances IgnoreNew `
  -Hidden
# Explicitly do NOT wake the PC — WakeToRun caused console flashes on plug-in / resume
try { $settings.WakeToRun = $false } catch {}
try { $settings.DisallowStartIfOnBatteries = $false } catch {}

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

try {
  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Silent health check: restarts trading agent if heartbeat dies (every 5 min, hidden, no wake)" `
    -Force | Out-Null
  Write-Output "Installed scheduled task: $TaskName (hidden, every 5 min, no WakeToRun)"
} catch {
  $tr = "`"$Python`" `"$Script`""
  cmd /c "schtasks /Create /TN $TaskName /TR $tr /SC MINUTE /MO 5 /F /RL LIMITED /IT"
  Write-Output "Installed scheduled task via schtasks fallback: $TaskName"
}

& "$Root\scripts\install_autostart.ps1"
