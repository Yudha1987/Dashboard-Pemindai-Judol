# -*- coding: utf-8 -*-
"""
Pemantau & Scanner Website Kabupaten Ngawi
- Indikasi sisipan judi online / slot / gacor / toto / spam SEO asing.

Mendukung 2 profil independen (--profile):
  opd  : OPD, Kecamatan, Puskesmas & RS (domain *.ngawikab.go.id), port 8000
  desa : Website Desa Pengguna OpenSID (*.desa.id), port 8001

Cara pakai:
  python main.py --profile=desa --once            # scan desa sekali lalu keluar
  python main.py --profile=opd  --serve           # dashboard OPD (port 8000)
  python main.py --profile=desa --serve           # dashboard Desa (port 8001)
  python main.py --once --interactive             # scan + jelajah hasil interaktif
  python main.py --watch                          # scan berulang (default 30 menit)
  python main.py --serve --port=8001 --interval-min=60

Konfigurasi environment:
  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID   (atau file .env)
  CONCURRENCY=10  TIMEOUT=25  RETRIES=2
  DEEP_SCAN_ENABLED=1  DEEP_SCAN_PAGES=20  DEEP_SCAN_THREADS=3
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from colorama import Fore, Style, init

from config.config import CONCURRENCY
from config.profiles import get_profile
from src.reporter import (
    interactive_browse, print_header, print_summary, print_table,
    sort_results, write_report,
)
from src.scanner import scan_target
from src.telegram_alert import send_telegram_alert

init(autoreset=True)

# Console Windows tidak bisa encode semua karakter Unicode; jangan crash.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(errors="replace")
        except (ValueError, OSError):
            pass

AUTO_REFRESH_SEC = 45


# --- Proteksi akses dashboard lomba (Basic Auth) ---
_LOMBA_AUTH_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "lomba_auth.json")
_LOMBA_USER = "admin"


def _load_lomba_creds():
    """Muat username/password proteksi dashboard lomba.

    Prioritas: env LOMBA_USER / LOMBA_PASS -> file config/lomba_auth.json ->
    dibuat otomatis dengan password acak (disimpan + dicetak).
    """
    user = os.environ.get("LOMBA_USER") or _LOMBA_USER
    env_pass = os.environ.get("LOMBA_PASS")
    store = None
    try:
        if os.path.exists(_LOMBA_AUTH_FILE):
            with open(_LOMBA_AUTH_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
    except (OSError, ValueError):
        store = None
    if env_pass:
        pwd = env_pass
        generated = False
    elif store and store.get("user") == user and store.get("password"):
        pwd = store["password"]
        generated = False
    else:
        pwd = secrets.token_urlsafe(12)
        generated = True
        try:
            os.makedirs(os.path.dirname(_LOMBA_AUTH_FILE), exist_ok=True)
            with open(_LOMBA_AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump({"user": user, "password": pwd}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return user, pwd, generated


def _check_basic_auth(self):
    """Validasi Basic Auth; kirim 401 bila tidak sesuai. Return True jika lolos."""
    header = self.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Lomba Dashboard"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False
    try:
        raw = base64.b64decode(header[6:]).decode("utf-8")
    except Exception:
        raw = ""
    given_user, _, given_pass = raw.partition(":")
    if (hmac.compare_digest(given_user, _LOMBA_USER)
            and hmac.compare_digest(given_pass, _LOMBA_PASS)):
        return True
    self.send_response(401)
    self.send_header("WWW-Authenticate", 'Basic realm="Lomba Dashboard"')
    self.send_header("Content-Length", "0")
    self.end_headers()
    return False


def run_scan(concurrency, output_dir, verbose=True, state=None,
             auto_refresh=0, interactive=False, single_url=None, profile=None):
    p = get_profile(profile)
    targets = p["targets"]
    if single_url:
        targets = [t for t in targets if t["url"] == single_url]
        if not targets:
            default_cat = "OPD" if p["key"] == "opd" else "DESA"
            targets = [{"name": single_url, "url": single_url, "category": default_cat}]

    total = len(targets)
    if state is not None:
        with state.lock:
            state.progress = {"done": 0, "total": total}
    if verbose:
        print_header(p)
        print(Fore.CYAN + "[+] Memulai pemindaian %d target %s ..."
              % (total, p["count_label"]))
        print(Fore.CYAN + "[+] Waktu mulai : %s" % datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        print()

    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(scan_target, t): t for t in targets}
        for future in as_completed(futures):
            done += 1
            if state is not None:
                with state.lock:
                    state.progress["done"] = done
            r = future.result()
            results.append(r)
            # Instant Alert: kirim notifikasi Telegram SEGERA (async) begitu
            # satu target terdeteksi judi/spam, tanpa menunggu selesai.
            if r["status"] == "DETECTED":
                send_telegram_alert(r, scope=p["scope"], entity=p["entity"])
            if verbose:
                status_dot = {
                    "DETECTED": Fore.RED + "!!",
                    "AMAN": Fore.GREEN + "OK",
                    "OFFLINE": Fore.YELLOW + "--",
                }[r["status"]]
                sys.stdout.write(
                    "\r[%d/%d] %s %-24s %s %s"
                    % (done, total, status_dot, r["name"],
                       Style.RESET_ALL, r["url"])
                )
                sys.stdout.flush()

    if verbose:
        print("\n")

    results_sorted = sort_results(results)
    if verbose:
        print_table(results_sorted, profile=p)
        print_summary(results_sorted)

    html_path = write_report(results_sorted, output_dir, auto_refresh=auto_refresh,
                             profile=p)
    if verbose:
        print(Fore.CYAN + "[+] Dashboard HTML : %s" % os.path.abspath(html_path))
        print(Fore.CYAN + "[+] Snapshot JSON  : %s"
              % os.path.abspath(os.path.join(output_dir, p["json_name"])))
        print(Fore.CYAN + "[+] Snapshot CSV   : %s"
              % os.path.abspath(os.path.join(output_dir, p["csv_name"])))
        print()

    if interactive:
        try:
            interactive_browse(results_sorted, profile=p)
        except (EOFError, KeyboardInterrupt):
            pass

    if state is not None:
        with state.lock:
            with open(html_path, "r", encoding="utf-8") as f:
                state.html = f.read()
            json_path = os.path.join(output_dir, p["json_name"])
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    state.snapshot = json.load(f)
            except (OSError, ValueError):
                state.snapshot = {}
            state.last_update = datetime.now()
            state.summary = {
                "total": len(results_sorted),
                "detected": sum(1 for r in results_sorted if r["status"] == "DETECTED"),
                "safe": sum(1 for r in results_sorted if r["status"] == "AMAN"),
                "offline": sum(1 for r in results_sorted if r["status"] == "OFFLINE"),
                "critical": sum(1 for r in results_sorted if r.get("critical")),
            }
            state.scanning = False

    return results_sorted


class ServeState:
    def __init__(self):
        self.lock = threading.Lock()
        self.html = ""
        self.snapshot = {}
        self.last_update = None
        self.summary = {}
        self.scanning = False
        self.progress = {"done": 0, "total": 0}


def _start_background_scan(state, concurrency, output_dir, verbose=False, profile=None):
    with state.lock:
        if state.scanning:
            return False
        state.scanning = True
    threading.Thread(
        target=_scan_worker,
        args=(state, concurrency, output_dir, verbose, profile),
        daemon=True,
    ).start()
    return True


def _scan_worker(state, concurrency, output_dir, verbose=False, profile=None):
    try:
        run_scan(concurrency, output_dir, verbose=verbose,
                 state=state, auto_refresh=AUTO_REFRESH_SEC, profile=profile)
        if profile == "desa":
            _regenerate_lomba_dashboard()
    except Exception as e:  # noqa: BLE001
        with state.lock:
            state.scanning = False
        print(Fore.RED + "[!] Kesalahan saat pemindaian: %s" % e)


def _regenerate_lomba_dashboard():
    """Regenerate lomba dashboard after desa scan completes."""
    try:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "gen_lomba_dashboard.py")
        subprocess.run(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True, timeout=60
        )
    except Exception:
        pass


def make_handler(state, concurrency, output_dir, profile=None):
    p = get_profile(profile)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, ctype, body):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, obj):
            self._send(200, "application/json; charset=utf-8",
                       json.dumps(obj, ensure_ascii=False))

        def _schedule_scan(self):
            return _start_background_scan(state, concurrency, output_dir,
                                          profile=p)

        def do_GET(self):
            path, _, qs = self.path.partition("?")
            query = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
            if path.startswith("/lomba") or path.startswith("/api/lomba"):
                if not _check_basic_auth(self):
                    return
            if path in ("/", "/dashboard.html"):
                if query.get("noauto") != "1":
                    self._schedule_scan()
                with state.lock:
                    html = state.html
                if not html:
                    html = ("<html><body><h3>Memindai pertama kali, "
                            "silahkan reload dalam beberapa saat...</h3></body></html>")
                self._send(200, "text/html; charset=utf-8", html)
            elif path in ("/last_scan.json", "/" + p["json_name"]):
                with state.lock:
                    self._send_json(state.snapshot)
            elif path == "/api/status":
                with state.lock:
                    self._send_json({
                        "scanning": state.scanning,
                        "last_update": state.last_update.strftime("%d/%m/%Y %H:%M:%S")
                        if state.last_update else None,
                        "summary": state.summary,
                        "progress": dict(state.progress),
                    })
            elif path == "/api/scan":
                started = self._schedule_scan()
                self._send_json({"status": "started" if started else "already_scanning"})
            elif path == "/logo.png":
                logo_path = os.path.join(output_dir, "logo.png")
                try:
                    with open(logo_path, "rb") as f:
                        self._send(200, "image/png", f.read())
                except OSError:
                    self._send(404, "text/plain; charset=utf-8", "logo tidak ditemukan")
            elif path == "/logo_ngawi.png":
                logo_path = os.path.join(output_dir, "logo_ngawi.png")
                try:
                    with open(logo_path, "rb") as f:
                        self._send(200, "image/png", f.read())
                except OSError:
                    self._send(404, "text/plain; charset=utf-8", "logo tidak ditemukan")
            elif path.startswith("/assets/"):
                asset_name = path[len("/assets/"):]
                asset_path = os.path.join(output_dir, "assets", asset_name)
                try:
                    if asset_name.endswith(".svg"):
                        mime = "image/svg+xml"
                    elif asset_name.endswith(".jpg") or asset_name.endswith(".jpeg"):
                        mime = "image/jpeg"
                    else:
                        mime = "image/png"
                    with open(asset_path, "rb") as f:
                        self._send(200, mime, f.read())
                except OSError:
                    self._send(404, "text/plain; charset=utf-8", "asset tidak ditemukan")
            elif path in ("/lomba", "/lomba/"):
                lomba_path = os.path.join(os.path.dirname(output_dir), "lomba", "dashboard.html")
                try:
                    with open(lomba_path, "r", encoding="utf-8") as f:
                        self._send(200, "text/html; charset=utf-8", f.read())
                except OSError:
                    self._send(404, "text/plain; charset=utf-8", "dashboard lomba tidak ditemukan")
            elif path == "/api/lomba/nilai":
                self._send_json(self._load_lomba_nilai())
            elif path == "/api/lomba/skor":
                self._send_json(self._load_lomba_skor())
            elif path.startswith("/lomba/") and path.endswith(".json"):
                rel = os.path.basename(path)
                jp = os.path.join(os.path.dirname(output_dir), "lomba", rel)
                try:
                    with open(jp, "r", encoding="utf-8") as f:
                        self._send(200, "application/json; charset=utf-8", f.read())
                except OSError:
                    self._send(404, "text/plain; charset=utf-8", "file tidak ditemukan")
            else:
                self._send(404, "text/plain; charset=utf-8",
                           "Not found. Buka http://127.0.0.1:%s/dashboard.html"
                           % self.server.server_port)

        def _lomba_dir(self):
            return os.path.join(os.path.dirname(output_dir), "lomba")

        def _load_lomba_nilai(self):
            p = os.path.join(self._lomba_dir(), "nilai_juri.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, ValueError):
                    pass
            return {}

        def _load_lomba_skor(self):
            p = os.path.join(self._lomba_dir(), "skor_summary.json")
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, ValueError):
                    pass
            return []

        def do_POST(self):
            path, _, _ = self.path.partition("?")
            if path.startswith("/api/lomba"):
                if not _check_basic_auth(self):
                    return
            if path == "/api/lomba/nilai":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length) if length else b"{}"
                    payload = json.loads(body.decode("utf-8") or "{}")
                except Exception:
                    self._send(400, "application/json; charset=utf-8",
                               json.dumps({"status": "error", "message": "JSON tidak valid"}))
                    return
                desa = payload.get("desa")
                if not desa:
                    self._send(400, "application/json; charset=utf-8",
                               json.dumps({"status": "error", "message": "field 'desa' wajib"}))
                    return
                store = self._load_lomba_nilai()
                nilai = {k: v for k, v in payload.items() if k != "desa"}
                if all(v is None or v == "" for v in nilai.values()):
                    store.pop(desa, None)
                else:
                    store[desa] = {k: v for k, v in nilai.items() if v is not None and v != ""}
                p = os.path.join(self._lomba_dir(), "nilai_juri.json")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(store, f, ensure_ascii=False, indent=2)
                    _regenerate_lomba_dashboard()
                    self._send_json({"status": "ok", "message": "Nilai tersimpan untuk %s" % desa})
                except OSError as e:
                    self._send_json({"status": "error", "message": "Gagal menyimpan: %s" % e})
                return
            self._send(404, "text/plain; charset=utf-8", "Not found")

        def log_message(self, *args):  # noqa: A003
            pass

    return Handler


def _ensure_assets(output_dir):
    """Salin logo ke folder output profil jika belum ada."""
    os.makedirs(output_dir, exist_ok=True)
    legacy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    for name in ("logo.png", "logo_ngawi.png"):
        dst = os.path.join(output_dir, name)
        if os.path.exists(dst):
            continue
        src = os.path.join(legacy_dir, name)
        if os.path.exists(src):
            try:
                with open(src, "rb") as fin, open(dst, "wb") as fout:
                    fout.write(fin.read())
            except OSError:
                pass


def serve_mode(concurrency, output_dir, port, interval_min, profile=None, host=None):
    if not host:
        host = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
    global _LOMBA_USER, _LOMBA_PASS
    _LOMBA_USER, _LOMBA_PASS, _lomba_gen = _load_lomba_creds()
    p = get_profile(profile)
    _ensure_assets(output_dir)
    state = ServeState()

    html_path = os.path.join(output_dir, p["html_name"])
    if os.path.exists(html_path):
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                state.html = f.read()
        except OSError:
            pass
    json_path = os.path.join(output_dir, p["json_name"])
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                state.snapshot = json.load(f)
        except (OSError, ValueError):
            pass

    handler = make_handler(state, concurrency, output_dir, profile=p)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(Style.BRIGHT + "=" * 78)
    print("  DASHBOARD SERVER AKTIF")
    print("  %s" % p["subject"])
    print("  Buka local : http://127.0.0.1:%d/dashboard.html" % port)
    print("  LAN/Internet: http://<IP-atau-host>:%d (bind %s)" % (port, host))
    print("  Auto-scan : saat dibuka + terjadwal setiap %d menit" % interval_min)
    print("  Proteksi  : Basic Auth user=%s (lihat config/lomba_auth.json)" % _LOMBA_USER)
    if _lomba_gen:
        print("  PASSWORD  : %s  <-- dibuat baru, bagikan ke pengguna" % _LOMBA_PASS)
    print("  Stop      : Ctrl+C")
    print("=" * 78 + Style.RESET_ALL)

    schedule_sec = max(60, interval_min * 60)

    def _scheduler():
        while True:
            time.sleep(schedule_sec)
            started = _start_background_scan(state, concurrency, output_dir,
                                             profile=p)
            if started:
                print(Fore.CYAN + "[+] Scan terjadwal dimulai (%s)"
                      % datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    threading.Thread(target=_scheduler, daemon=True).start()

    print(Fore.CYAN + "[+] Scan otomatis saat dibuka dimulai ...")
    _start_background_scan(state, concurrency, output_dir, verbose=True, profile=p)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main():
    parser = argparse.ArgumentParser(
        description="Pemantau website indikasi judi online / spam - Kab. Ngawi"
    )
    parser.add_argument("--profile", choices=["opd", "desa"], default="desa",
                        help="profil target: desa (*.desa.id) atau opd "
                             "(*.ngawikab.go.id) (default: desa)")
    parser.add_argument("--once", action="store_true", help="scan satu kali lalu keluar")
    parser.add_argument("--watch", action="store_true", help="mode pemantauan terjadwal")
    parser.add_argument("--serve", action="store_true",
                        help="sajikan dashboard via server lokal")
    parser.add_argument("--port", type=int, default=None,
                        help="port server dashboard (default: 8000 untuk OPD, "
                             "8001 untuk Desa)")
    parser.add_argument("--host", default=None,
                        help="host/alamat binding server dashboard "
                             "(default: 0.0.0.0 = semua antarmuka LAN)")
    parser.add_argument("--interval-min", type=int, default=None,
                        help="interval scan ulang dalam menit (default: "
                             "--serve=1440 [1x sehari], --watch=30)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY,
                        help="jumlah scan paralel (default: %d)" % CONCURRENCY)
    parser.add_argument("--output", default=None, help="folder hasil scan "
                                                       "(default per profil)")
    parser.add_argument("--interactive", action="store_true",
                        help="jelajahi hasil scan secara interaktif")
    parser.add_argument("--single", default=None, metavar="URL",
                        help="scan satu website saja")
    parser.add_argument("--deep-scan-pages", type=int, default=None,
                        help="maks halaman dalam yang di-scan per website via sitemap")
    parser.add_argument("--no-deep-scan", action="store_true",
                        help="nonaktifkan deep-scan via sitemap")
    args = parser.parse_args()

    if args.concurrency < 1:
        args.concurrency = 1
    if args.deep_scan_pages is not None:
        os.environ["DEEP_SCAN_PAGES"] = str(args.deep_scan_pages)
    if args.no_deep_scan:
        os.environ["DEEP_SCAN_ENABLED"] = "0"

    p = get_profile(args.profile)
    output_dir = args.output if args.output is not None else p["output_dir"]

    if args.serve:
        port = args.port if args.port is not None else p["port"]
        interval_min = (args.interval_min if args.interval_min is not None
                        else int(os.environ.get(
                            "SCAN_INTERVAL_MIN", str(p["default_interval_min"]))))
        serve_mode(args.concurrency, output_dir, port, interval_min, profile=p,
                   host=args.host)
        return

    if args.once or args.single:
        run_scan(args.concurrency, output_dir, interactive=args.interactive,
                 single_url=args.single, profile=p)
        return

    interval_min = (args.interval_min if args.interval_min is not None
                    else int(os.environ.get("SCAN_INTERVAL_MIN", "30")))
    interval_sec = interval_min * 60
    print(Style.BRIGHT + "PEMANTAU BERJALAN (WATCH MODE)")
    print("Profil: %s | Interval scan ulang: %d menit | Paralel: %d | "
          "Tekan Ctrl+C untuk berhenti."
          % (p["subject"], interval_min, args.concurrency))
    print("=" * 78)

    while True:
        start = time.time()
        try:
            run_scan(args.concurrency, output_dir, profile=p)
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            print(Fore.RED + "[!] Kesalahan saat pemindaian: %s" % e)
        elapsed = time.time() - start
        sleep_for = max(5, interval_sec - elapsed)
        print(Fore.YELLOW + "[.] Scan berikutnya dalam %d menit ..." % (sleep_for / 60))
        try:
            time.sleep(sleep_for)
        except KeyboardInterrupt:
            print()
            print(Style.BRIGHT + "Pemantau dihentikan.")
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDihentikan oleh pengguna.")
        sys.exit(0)
