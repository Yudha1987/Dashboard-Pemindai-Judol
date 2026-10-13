@echo off
rem Detached launcher watchdog server OPD + desa (tanpa admin).
set PY=C:\Users\komin\Documents\Default Project\ngawi-website-scanner\.venv\Scripts\python.exe
set WD=C:\Users\komin\Documents\Default Project\desa-opensid-monitor\scripts\server_watchdog.py
start "watchdog-server" /MIN "%PY%" "%WD%"