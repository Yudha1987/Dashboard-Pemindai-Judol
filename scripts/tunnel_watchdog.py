# -*- coding: utf-8 -*-
"""
Watchdog tunnel Cloudflare (quick tunnel) untuk dashboard lomba.

Tugas:
1. Pastikan proses cloudflared selalu berjalan (restart otomatis bila mati).
2. Baca URL trycloudflare terbaru dari log cloudflared.
3. Bandingkan dengan URL terakhir yang tersimpan; jika BERUBAH / pertama kali,
   kirim notifikasi Telegram dengan link dashboard baru.
4. Log aktivitas ke %LOCALAPPDATA%/Temp/opencode/cloudflared_watchdog.log

Dijalankan terpisah (tidak bergantung terminal) dari:
    cmd /c start "" /MIN <python> tunnel_watchdog.py
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import src.telegram_alert as ta  # reuse env + sender

CF_EXE = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
CF_LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp", "opencode", "cloudflared")
CF_LOG = os.path.join(CF_LOG_DIR, "cloudflared.log")
CF_LOG_ERR = CF_LOG + ".err"
WATCH_LOG = os.path.join(os.environ.get("LOCALAPPDATA", "."), "Temp", "opencode",
                         "cloudflared_watchdog.log")
STATE_FILE = os.path.join(PROJECT_ROOT, "output", "lomba", "tunnel_url_state.json")
LOCK_FILE = os.path.join(CF_LOG_DIR, "watchdog.pid")
POLL_SEC = 20
WAIT_URL_SEC = 120
URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


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


def tunnel_running():
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
            stderr=subprocess.STDOUT, timeout=15).decode("utf-8", "replace")
        return "cloudflared.exe" in out
    except Exception:
        return None  # tidak bisa memastikan


def extract_url():
    if not os.path.exists(CF_LOG):
        return None
    try:
        with open(CF_LOG, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except OSError:
        return None
    for line in reversed(data.splitlines()):
        m = URL_RE.search(line)
        if m:
            return m.group(0)
    return None


def start_tunnel():
    for p in (CF_LOG, CF_LOG_ERR):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass
    sw = subprocess.STARTUPINFO()
    sw.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(os.devnull, "wb") as dn:
        subprocess.Popen(
            [CF_EXE, "tunnel", "--url", "http://127.0.0.1:8001",
             "--no-autoupdate", "--logfile", CF_LOG, "--loglevel", "info"],
            stdin=dn, stdout=dn, stderr=dn,
            creationflags=flags, startupinfo=sw, close_fds=True)
    wlog("cloudflared diluncurkan (detached)")


def read_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(url, restarts):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url, "restarts": restarts,
                   "updated_at": now()}, f, ensure_ascii=False, indent=2)


try:
    if not acquire_lock():
        wlog("watchdog lain sudah berjalan, keluar.")
        sys.exit(0)
except Exception as exc:  # noqa: BLE001
    wlog("gagal acquire lock: %s" % exc)

wlog("Watchdog tunnel lomba dimulai (PID %s)." % os.getpid())

restarts = int(read_state().get("restarts", 0))

while True:
    running = tunnel_running()
    url = extract_url()

    if not running:
        wlog("cloudflared TIDAK jalan -> restart")
        restarts += 1
        start_tunnel()
        deadline = time.time() + WAIT_URL_SEC
        url = None
        while time.time() < deadline:
            time.sleep(5)
            if extract_url():
                url = extract_url()
                break
            if tunnel_running() is False:
                break
        if not url:
            wlog("tidak mendapat URL setelah restart (log kosong).")
    else:
        # proses jalan; pastikan kita punya URL tercatat
        if not url and os.path.exists(CF_LOG):
            wlog("cloudflared jalan tapi URL belum terdeteksi di log.")

    state = read_state()
    last = state.get("url")

    if url and url != last:
        first = not last
        try:
            ta._load_env()
            ok = False
            if ta.BOT_TOKEN and ta.CHAT_ID:
                ok = ta._send_sync(
                    ("\U0001F3D5 \u2b50 *LOMBA DASHBOARD%s*\n"
                     "----------------------------\n"
                     "URL: %s/lomba\n"
                     "Login: user `admin`"
                     % (" - Link Aktif" if first else " - Link Berubah", url)))
            wlog("URL -> %s (first=%s) telegram_ok=%s" % (url, first, ok))
        except Exception as exc:  # noqa: BLE001
            wlog("gagal kirim telegram: %s" % exc)
        save_state(url, restarts)
    else:
        # tidak ada perubahan; simpan reset count jika berbeda tapi url sama
        if state.get("restarts") != restarts:
            save_state(url or last, restarts) if url else None

    time.sleep(POLL_SEC)