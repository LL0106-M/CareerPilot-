@echo off
rem ============================================================
rem CareerPilot - independent persistent service launcher
rem Starts backend (uvicorn :8000) and ngrok tunnel as separate,
rem persistent Windows processes. Safe to close this window.
rem ============================================================
setlocal
cd /d "%~dp0.."

rem ngrok free plan refuses to run with http_proxy set
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=

start "CareerPilot-Backend" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_local_production.ps1" -Port 8000
timeout /t 3 /nobreak >nul
start "CareerPilot-Ngrok" /min "%~dp0..\ngrok.exe" http --url=palace-marbles-whoever.ngrok-free.dev 8000

echo.
echo CareerPilot backend and ngrok tunnel started as independent processes.
echo Public URL: https://palace-marbles-whoever.ngrok-free.dev
echo ngrok inspector: http://127.0.0.1:4040
echo To stop: close the two minimized windows, or run stop_all_services.bat
endlocal
pause
