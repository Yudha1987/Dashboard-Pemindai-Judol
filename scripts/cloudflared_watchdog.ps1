# -*- coding: utf-8 -*-
# Watchdog: pastikan cloudflared tunnel tetap berjalan.
# Jika proses keluar, restart otomatis. Jalankan via task scheduler / startup.
$cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$logDir = "$env:LOCALAPPDATA\Temp\opencode"
while ($true) {
    $proc = Get-Process cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $proc) {
        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path "$logDir\cloudflared_watchdog.log" -Value "$ts RESTART cloudflared"
        Start-Process -FilePath $cf -ArgumentList "tunnel","--url","http://127.0.0.1:8001","--no-autoupdate" `
            -RedirectStandardOutput "$logDir\cloudflared.log" `
            -RedirectStandardError "$logDir\cloudflared.log.err" `
            -WindowStyle Hidden
    }
    Start-Sleep -Seconds 30
}