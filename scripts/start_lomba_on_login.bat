@echo off
rem Startup: server OPD (8000) + server dashboard lomba (8001) + cloudflared tunnel
rem saat login. Keduanya auto-scan saat dibuka + terjadwal setiap 2 jam (120 menit).
set BASE=C:\Users\komin\Documents\Default Project\desa-opensid-monitor
set PY=C:\Users\komin\Documents\Default Project\ngawi-website-scanner\.venv\Scripts\python.exe
set SCRIPTS=%BASE%\scripts
cd /d "%BASE%"

rem OPD server (port 8000)
netstat -ano | findstr /R /C:":8000 .*LISTENING" >nul
if errorlevel 1 (
    start "opd-server" /MIN "%PY%" "%BASE%\main.py" --serve --profile=opd --port=8000 --interval-min=120
)

rem Desa/lomba server (port 8001)
netstat -ano | findstr /R /C:":8001 .*LISTENING" >nul
if errorlevel 1 (
    start "lomba-server" /MIN "%PY%" "%BASE%\main.py" --serve --profile=desa --port=8001 --interval-min=120
)

tasklist /FI "IMAGENAME eq cloudflared.exe" 2>nul | find /I "cloudflared.exe" >nul
if errorlevel 1 (
    call "%SCRIPTS%\tunnel_lomba.bat"
)

rem watchdog tunnel (auto-restart + notif link baru via Telegram)
call "%SCRIPTS%\watchdog_lomba.bat"

rem watchdog server (pastikan server OPD & desa selalu hidup sampai PC mati)
call "%SCRIPTS%\server_watchdog.bat"