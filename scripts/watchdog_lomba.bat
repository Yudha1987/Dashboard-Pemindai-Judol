@echo off
rem Detached launcher watchdog tunnel lomba (tanpa admin).
set PY=C:\Users\komin\Documents\Default Project\ngawi-website-scanner\.venv\Scripts\python.exe
set WD=C:\Users\komin\Documents\Default Project\desa-opensid-monitor\scripts\tunnel_watchdog.py
start "watchdog-lomba" /MIN "%PY%" "%WD%"