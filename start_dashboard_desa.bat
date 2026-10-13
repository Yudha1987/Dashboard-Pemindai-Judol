@echo off
setlocal EnableExtensions
title Pemantau Website Desa - Dashboard
cd /d "%~dp0"

rem Hentikan server lama di port 8001 (jika masih berjalan)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001 " ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)

rem Pilih interpreter Python (prioritas: venv proyek, lalu python sistem)
set "PY=%~dp0..\ngawi-website-scanner\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
if not exist "%PY%" (
    echo Python tidak ditemukan. Pastikan Python sudah terinstall.
    pause
    exit /b 1
)

rem Hitung jumlah target dari data/targets.py
set "TARGET_COUNT=?"
"%PY%" -c "import sys;sys.path.insert(0,'.');from data.targets import TARGETS;open('target_count.tmp','w').write(str(len(TARGETS)))" >nul 2>&1
if exist target_count.tmp (
    set /p TARGET_COUNT=<target_count.tmp
    del target_count.tmp >nul 2>&1
)

echo ============================================================
echo    Pemantau Website Desa Kab. Ngawi
echo    Target   : %TARGET_COUNT% website desa (.desa.id)
echo    Dashboard: http://127.0.0.1:8001/dashboard.html
echo    Mode     : scan otomatis + dashboard (rescan tiap 24 jam)
echo ============================================================
echo.
echo Menjalankan scan dan memulai server dashboard...
echo Jangan tutup jendela ini agar server tetap berjalan.
echo.
echo Membuka dashboard di browser secara otomatis...
start "" /min cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8001/dashboard.html"

"%PY%" main.py --serve --profile=desa --port=8001 --interval-min=1440

echo.
echo Server dashboard dihentikan.
pause
