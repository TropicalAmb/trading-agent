@echo off
cd /d C:\Users\patri\trading-agent
title Start Trading Agent
color 0A
echo.
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python venv not found at C:\Users\patri\trading-agent\.venv
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\start_agent.py"
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Start finished with code %EXITCODE%.
  pause
)
exit /b %EXITCODE%
