@echo off
REM Stop trading agent silently (no nested PowerShell flash)
cd /d "%~dp0\.."
".venv\Scripts\python.exe" "scripts\stop_agent.py"
if errorlevel 1 (
  echo Stop reported an error. Check data\watchdog.log
  pause
  exit /b 1
)
echo Agent stopped. Window will close.
timeout /t 2 /nobreak >nul
