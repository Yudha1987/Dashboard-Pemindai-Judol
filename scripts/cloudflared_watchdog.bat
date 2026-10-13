@echo off
rem Watchdog cloudflared tunnel untuk dashboard lomba.
rem Restart cloudflared otomatis jika mati. Jalankan sekali: cmd /c watchdog.bat
set CF="C:\Program Files (x86)\cloudflared\cloudflared.exe"
set LOGDIR=%LOCALAPPDATA%\Temp\opencode
:loop
tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
if errorlevel 1 (
    echo %date% %time% RESTART cloudflared >> "%LOGDIR%\cloudflared_watchdog.log"
    start "cloudflared" /MIN "%CF%" tunnel --url http://127.0.0.1:8001 --no-autoupdate
)
timeout /t 30 /nobreak >nul
goto loop