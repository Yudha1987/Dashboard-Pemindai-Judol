@echo off
rem Detached launcher untuk cloudflared tunnel dashboard lomba (dipanggil tanpa admin).
set CF="C:\Program Files (x86)\cloudflared\cloudflared.exe"
set LOG=%LOCALAPPDATA%\Temp\opencode\cloudflared\cloudflared.log
if not exist "%LOCALAPPDATA%\Temp\opencode\cloudflared\" mkdir "%LOCALAPPDATA%\Temp\opencode\cloudflared"
start "cloudflared-lomba" /MIN %CF% tunnel --url http://127.0.0.1:8001 --no-autoupdate --logfile "%LOG%" --loglevel info