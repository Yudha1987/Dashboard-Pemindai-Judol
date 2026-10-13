# -*- coding: utf-8 -*-
"""Entrypoint WSGI untuk deployment di Vercel / WSGI server.

Vercel mendeteksi ``main.py`` sebagai entrypoint Python dan mewajibkan variabel
top-level ``app`` / ``application`` / ``handler``. Modul ini membungkus scanner
(DESA / OPD) menjadi aplikasi WSGI sehingga bisa dijalankan sebagai Vercel Function.

Sumber data dashboard (berurutan):
  1. Cache di memori (hasil scan pada instance yang masih hangat).
  2. Snapshot ter-commit: output/<profile>/results_<profile>.json
  3. Hasil scan on-demand di /tmp (serverless).

Profil yang disajikan diatur lewat env ``VERCEL_PROFILE`` (default: desa).

Endpoint:
  GET /                 -> dashboard HTML
  GET /dashboard.html   -> dashboard HTML
  GET /results/desa.json
  GET /results/opd.json -> snapshot JSON
  GET /last_scan.json   -> alias snapshot profil aktif
  GET /api/status       -> status ringkas
  GET /api/scan         -> scan terbatas (sinkron) lalu hasilnya disatukan
  GET /logo.png, /logo_ngawi.png, /assets/* -> logo & aset statis
  GET /healthz          -> health check

Catatan serverless: Vercel Function punya batas waktu, jadi scan penuh seluruh
target sebaiknya dijalankan terjadwal (mis. GitHub Actions) dan hasilnya
di-commit kembali. Endpoint ``/api/scan`` hanya memindai sebagian target
(env ``VERCEL_SCAN_LIMIT``, default 12).
"""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from src import reporter
from src.scanner import scan_target
from src.telegram_alert import send_telegram_alert
from config.profiles import get_profile

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_MIME_BY_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".css": "text/css",
    ".js": "text/javascript",
}


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _active_profile():
    key = os.environ.get("VERCEL_PROFILE") or "desa"
    return get_profile(key)


def _snapshot_candidates(p):
    return [
        os.path.join(_PROJECT_ROOT, p["output_dir"], p["json_name"]),
        os.path.join("/tmp", "ngawi_dashboard", p["key"], p["json_name"]),
    ]


def _writable_dir(p):
    """Direktori yang bisa ditulis (Vercel hanya mengizinkan /tmp)."""
    if os.environ.get("VERCEL") or not os.access(_PROJECT_ROOT, os.W_OK):
        target = os.path.join("/tmp", "ngawi_dashboard", p["key"])
    else:
        target = os.path.join(_PROJECT_ROOT, p["output_dir"])
    try:
        os.makedirs(target, exist_ok=True)
    except OSError:
        target = os.path.join("/tmp", "ngawi_dashboard", p["key"])
        os.makedirs(target, exist_ok=True)
    return target


class AppState:
    def __init__(self):
        self.lock = threading.Lock()
        self.results = None
        self.scanned_at = None
        self.scanning = False


def _parse_scanned_at(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _load_from_disk(state, p):
    for path in _snapshot_candidates(p):
        try:
            with open(path, "r", encoding="utf-8") as f:
                snapshot = json.load(f)
        except (OSError, ValueError):
            continue
        results = snapshot.get("results")
        if isinstance(results, list):
            with state.lock:
                state.results = results
                state.scanned_at = _parse_scanned_at(snapshot.get("scanned_at"))
            return True
    return False


def _json_result(r):
    return {
        "name": r["name"],
        "category": r.get("category", ""),
        "kecamatan": r.get("kecamatan", ""),
        "url": r["url"],
        "status": r["status"],
        "http_status": r.get("http_status"),
        "error": r.get("error"),
        "platform": r.get("platform"),
        "opensid_version": r.get("opensid_version"),
        "spam_comments": r.get("spam_comments", []),
        "comment_system": r.get("comment_system"),
        "title": r.get("title", ""),
        "last_post": r.get("last_post"),
        "repeated_posts": r.get("repeated_posts", []),
        "keywords": r.get("keywords", []),
        "critical": r.get("critical", False),
        "foreign_scripts": r.get("foreign_scripts", []),
    }


def _snapshot_payload(results, scanned_at, p):
    results_sorted = reporter.sort_results(results)
    summary = reporter.summarize(results_sorted)
    return {
        "scanned_at": (scanned_at or datetime.now()).isoformat(),
        "profile": p["key"],
        "summary": {
            "total": summary["total"],
            "detected": summary["detected"],
            "safe": summary["safe"],
            "offline": summary["offline"],
            "critical": summary.get("critical", 0),
        },
        "results": [_json_result(r) for r in results_sorted],
    }


def _persist(state, p):
    with state.lock:
        results = list(state.results or [])
        scanned_at = state.scanned_at
    if not results:
        return
    payload = _snapshot_payload(results, scanned_at, p)
    target_dir = _writable_dir(p)
    try:
        with open(os.path.join(target_dir, p["json_name"]), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
    except OSError:
        pass


def _render_html(state, p):
    with state.lock:
        results = list(state.results or [])
        scanned_at = state.scanned_at
    results_sorted = reporter.sort_results(results)
    meta = reporter.summarize(results_sorted)
    meta["scanned_at"] = scanned_at or datetime.now()
    return reporter.render_html(results_sorted, meta, auto_refresh=0, profile=p)


def _run_scan(state, p, limit, concurrency):
    with state.lock:
        if state.scanning:
            return False
        state.scanning = True
    try:
        targets = p["targets"]
        if limit and limit > 0:
            targets = targets[:limit]
        results = []
        with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
            futures = [executor.submit(scan_target, t) for t in targets]
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception:  # noqa: BLE001
                    continue
                if result.get("status") == "DETECTED":
                    try:
                        send_telegram_alert(result, scope=p["scope"], entity=p["entity"])
                    except Exception:  # noqa: BLE001
                        pass
                results.append(result)
        with state.lock:
            merged = {r["url"]: r for r in (state.results or [])}
            for r in results:
                merged[r["url"]] = r
            state.results = list(merged.values())
            state.scanned_at = datetime.now()
            state.scanning = False
        _persist(state, p)
        return True
    finally:
        with state.lock:
            state.scanning = False


def _respond(start_response, status, content_type, body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    start_response(status, [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ])
    return [body]


def _respond_json(start_response, status, obj):
    return _respond(
        start_response, status,
        "application/json; charset=utf-8",
        json.dumps(obj, ensure_ascii=False, default=str),
    )


def _find_logo(p, name):
    """Cari file statis: output/<profile>/<name>, /tmp, atau folder output lama."""
    candidates = [
        os.path.join(_PROJECT_ROOT, p["output_dir"], name),
        os.path.join("/tmp", "ngawi_dashboard", p["key"], name),
        os.path.join(_PROJECT_ROOT, "output", name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _serve_static(start_response, path, p):
    rel = path.lstrip("/")
    if rel.startswith("assets/"):
        name = rel[len("assets/"):]
        ext = os.path.splitext(name)[1].lower()
        mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
        file_path = os.path.join(_PROJECT_ROOT, p["output_dir"], "assets", name)
        if not os.path.isfile(file_path):
            file_path = os.path.join(_PROJECT_ROOT, "assets", name)
        if not os.path.isfile(file_path):
            return _respond_json(start_response, "404 Not Found",
                                 {"error": "asset tidak ditemukan"})
        return _respond(start_response, "200 OK", mime, _read_binary(file_path))
    logo_path = _find_logo(p, rel)
    if logo_path:
        ext = os.path.splitext(rel)[1].lower()
        mime = _MIME_BY_EXT.get(ext, "image/png")
        return _respond(start_response, "200 OK", mime, _read_binary(logo_path))
    return _respond_json(start_response, "404 Not Found", {"error": "file tidak ditemukan"})


def _read_binary(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return b""


def build_wsgi_app():
    p = _active_profile()
    state = AppState()
    _load_from_disk(state, p)

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/") or "/"

        if path in ("/", "/dashboard.html", "/index.html"):
            html = _render_html(state, p)
            return _respond(start_response, "200 OK", "text/html; charset=utf-8", html)

        if path in ("/last_scan.json",
                    "/results/%s.json" % p["key"],
                    "/" + p["json_name"]):
            with state.lock:
                results = list(state.results or [])
                scanned_at = state.scanned_at
            payload = _snapshot_payload(results, scanned_at, p)
            return _respond_json(start_response, "200 OK", payload)

        if path == "/api/status":
            with state.lock:
                results = list(state.results or [])
                scanned_at = state.scanned_at
                scanning = state.scanning
            summary = reporter.summarize(results)
            return _respond_json(start_response, "200 OK", {
                "profile": p["key"],
                "scanning": scanning,
                "last_update": scanned_at.strftime("%d/%m/%Y %H:%M:%S") if scanned_at else None,
                "summary": {
                    "total": summary["total"],
                    "detected": summary["detected"],
                    "safe": summary["safe"],
                    "offline": summary["offline"],
                    "critical": summary.get("critical", 0),
                },
            })

        if path in ("/api/scan", "/scan"):
            limit = _env_int("VERCEL_SCAN_LIMIT", 12)
            concurrency = _env_int("VERCEL_SCAN_CONCURRENCY", 12)
            started = _run_scan(state, p, limit, concurrency)
            return _respond_json(start_response, "200 OK", {
                "status": "started" if started else "already_scanning",
                "profile": p["key"],
                "limit": 0 if limit <= 0 else limit,
            })

        if path in ("/logo.png", "/logo_ngawi.png") or path.startswith("/assets/"):
            return _serve_static(start_response, path, p)

        if path == "/healthz":
            return _respond_json(start_response, "200 OK", {"ok": True})

        return _respond_json(start_response, "404 Not Found", {"error": "not found"})

    return app