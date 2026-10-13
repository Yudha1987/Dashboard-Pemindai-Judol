@echo off
rem Detached launcher server dashboard lomba (port 8001).
cd /d "C:\Users\komin\Documents\Default Project\desa-opensid-monitor"
set PY=C:\Users\komin\Documents\Default Project\ngawi-website-scanner\.venv\Scripts\python.exe
set MAIN=C:\Users\komin\Documents\Default Project\desa-opensid-monitor\main.py
start "lomba-server" /MIN "%PY%" "%MAIN%" --serve --profile=desa --port=8001 --interval-min=120