@echo off
setlocal
title Izinkan Akses LAN Dashboard Pemindai Ngawi

rem ---------------------------------------------------------------
rem Membuka port dashboard agar bisa diakses dari perangkat lain
rem di jaringan LAN / Tailscale.
rem   Port 8000 = dashboard OPD
rem   Port 8001 = dashboard Desa / Pemindai
rem Wajib dijalankan sebagai Administrator:
rem   klik kanan file ini -> "Run as administrator"
rem ---------------------------------------------------------------

net session >nul 2>&1
if errorlevel 1 (
    echo [X] File ini harus dijalankan sebagai Administrator.
    echo     Klik kanan file ini lalu pilih "Run as administrator".
    echo.
    pause
    exit /b 1
)

echo [+] Menambahkan aturan firewall TCP 8000-8001 ...
netsh advfirewall firewall delete rule name="Dashboard Pemindai Ngawi (LAN)" >nul 2>&1
netsh advfirewall firewall add rule name="Dashboard Pemindai Ngawi (LAN)" dir=in action=allow protocol=TCP localport=8000-8001 profile=any enable=yes
if errorlevel 1 (
    echo [X] Gagal menambahkan aturan firewall.
    echo.
    pause
    exit /b 1
)

echo [OK] Aturan firewall aktif untuk port 8000 dan 8001.
echo.
echo Alamat akses (sesuaikan IP bila berubah):
echo   LAN       : http://192.168.1.2:8001/dashboard.html
echo   Tailscale : http://100.64.0.5:8001/dashboard.html
echo   Lokal     : http://127.0.0.1:8001/dashboard.html
echo.
echo Catatan:
echo   - Perangkat lain harus berada di Wi-Fi/LAN yang sama atau terhubung Tailscale.
echo   - Untuk mencabut aturan: jalankan perintah berikut sebagai Administrator:
echo       netsh advfirewall firewall delete rule name="Dashboard Pemindai Ngawi (LAN)"
echo.
pause
