# Register Windows Scheduled Task: start agent at login (HIDDEN, no console).
$ErrorActionPreference = "Stop"
$Root = "C:\Users\patri\trading-agent"
$PythonW = Join-Path $Root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $PythonW)) {
  $PythonW = Join-Path $Root ".venv\Scripts\python.exe"
}
$TaskName = "TradingAgentAutonomous"
$Script = Join-Path $Root "scripts\run_supervised.py"

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$Script`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
# No RestartOnFailure — the supervisor already restarts the agent itself.
# RestartOnFailure was spawning duplicate supervisors.
$settings = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries `
  -DontStopIfGoingOnBatteries `
  -DontStopOnIdleEnd `
  -StartWhenAvailable `
  -ExecutionTimeLimit (New-TimeSpan -Days 0) `
  -MultipleInstances IgnoreNew `
  -Hidden
try { $settings.WakeToRun = $false } catch {}
try { $settings.IdleSettings.StopOnIdleEnd = $false } catch {}

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

try {
  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Autonomous trading agent supervisor (hidden, no console, single instance)" `
    -Force | Out-Null
  Write-Output "Installed scheduled task: $TaskName (starts at Windows login, hidden)"
} catch {
  Write-Output "WARN: Could not register login task: $($_.Exception.Message)"
  Write-Output "Background bot still runs after Start Trading Agent (no console needed)."
  exit 0
}
