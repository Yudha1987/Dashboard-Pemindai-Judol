# -*- coding: utf-8 -*-
# Daftarkan Scheduled Task untuk dashboard lomba + tunnel cloudflare
# agar tetap hidup setelah reboot dan otomatis (tidak bergantung terminal).
$ErrorActionPreference = "Stop"

$cf = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$py = "C:\Users\komin\AppData\Local\Programs\Python\Python312\python.exe"
$src = "C:\Users\komin\Documents\Default Project\desa-opensid-monitor\main.py"
$work = "C:\Users\komin\Documents\Default Project\desa-opensid-monitor"
$lg = "$env:LOCALAPPDATA\Temp\opencode\cloudflared\cloudflared.log"

function New-SvcTask {
    param(
        [string]$Name,
        [string]$Action
    )
    $a = New-ScheduledTaskAction -Execute $Action
    $t = New-ScheduledTaskTrigger -AtStartup
    $s = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
    $p = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $Name -Action $a -Trigger $t -Settings $s -Principal $p -Force -Description "infra dashboard lomba" | Out-Null
    Write-Host "registered: $Name"
}

$tunCmd = "${cf} tunnel --url http://127.0.0.1:8001 --no-autoupdate --logfile `"${lg}`" --loglevel info"
New-SvcTask "LombaDashboardServer" "${py} `"${src}`" --serve --profile=desa --port=8001 --interval-min=1440"
New-SvcTask "LombaDashboardTunnel" $tunCmd