@echo off
rem Detached launcher server dashboard OPD (port 8000).
rem Scan otomatis: saat dibuka + terjadwal setiap 2 jam (120 menit).
cd /d "C:\Users\komin\Documents\Default Project\desa-opensid-monitor"
set PY=C:\Users\komin\Documents\Default Project\ngawi-website-scanner\.venv\Scripts\python.exe
set MAIN=C:\Users\komin\Documents\Default Project\desa-opensid-monitor\main.py
start "opd-server" /MIN "%PY%" "%MAIN%" --serve --profile=opd --port=8000 --interval-min=120