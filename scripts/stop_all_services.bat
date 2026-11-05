@echo off
rem ============================================================
rem CareerPilot - stop backend and ngrok processes
rem ============================================================
taskkill /IM ngrok.exe /F 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /PID %%p /F 2>nul
echo CareerPilot backend and ngrok stopped.
pause
