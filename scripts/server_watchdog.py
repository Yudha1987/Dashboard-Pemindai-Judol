# -*- coding: utf-8 -*-
"""
Watchdog server pemantauan (OPD + desa/OpenSID).

Tugas:
1. Pastikan server OPD (port 8000) selalu mendengarkan.
2. Pastikan server desa/lomba (port 8001) selalu mendengarkan.
3. Bila salah satu mati/crash -> hidupkan ulang via launcher .bat (profil + interval
   120 menit yang sama), sehingga siklus scan 2-jam terus berjalan hingga PC dimatikan.
4. Log ke %LOCALAPPDATA%/Temp/opencode/server_watchdog.log

Dijalankan terpisah (tidak bergantung terminal) dari:
    cmd /c start "" /MIN <python> server_watchdog.py
"""
import os
import socket
import subprocess
import sys
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
WATCH_LOG = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp", "opencode",
                         "server_watchdog.log")
LOCK_FILE = os.path.join(PROJECT_ROOT, "scripts", "server_watchdog.pid")
POLL_SEC = 20
BOOT_GRACE_SEC = 45

SERVERS = [
    {"name": "opd", "port": 8000, "bat": "server_opd.bat"},
    {"name": "desa", "port": 8001, "bat": "server_lomba.bat"},
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def wlog(msg):
    try:
        os.makedirs(os.path.dirname(WATCH_LOG), exist_ok=True)
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (now(), msg))
    except OSError:
        pass


def pid_alive(pid):
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
            stderr=subprocess.STDOUT, timeout=15).decode("utf-8", "replace")
        return str(pid) in out and "INFO" not in out.split(",")[-1]
    except Exception:
        return False


def acquire_lock():
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    if os.path.exists(LOCK_FILE):
        try:
            old = int(open(LOCK_FILE, "r").read().strip())
            if pid_alive(old):
                return False
        except (ValueError, OSError):
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def port_open(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start_server(server):
    bat = os.path.join(SCRIPTS_DIR, server["bat"])
    sw = subprocess.STARTUPINFO()
    sw.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(os.devnull, "wb") as dn:
        subprocess.Popen(["cmd", "/c", bat], stdin=dn, stdout=dn, stderr=dn,
                         cwd=PROJECT_ROOT, creationflags=flags,
                         startupinfo=sw, close_fds=True)
    wlog("%s (%s) diluncurkan ulang (detached)" % (server["name"], server["bat"]))


def main():
    try:
        if not acquire_lock():
            wlog("watchdog server lain sudah berjalan, keluar.")
            sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        wlog("gagal acquire lock: %s" % exc)

    wlog("Watchdog server OPD+desa dimulai (PID %s)." % os.getpid())

    cooldown = {}  # port -> timestamp (jangan spawn ulang sebelum ini)

    while True:
        for server in SERVERS:
            port = server["port"]
            if port_open(port):
                continue
            if time.time() < cooldown.get(port, 0):
                continue
            wlog("%s: port %d TIDAK mendengarkan -> restart" % (server["name"], port))
            start_server(server)
            cooldown[port] = time.time() + BOOT_GRACE_SEC
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()