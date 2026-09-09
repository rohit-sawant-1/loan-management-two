@echo off
REM Double-click this to start the whole project.
REM It just runs start-app.ps1, bypassing PowerShell's script-blocking policy
REM for this one run only (nothing changes system-wide).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-app.ps1"
pause
