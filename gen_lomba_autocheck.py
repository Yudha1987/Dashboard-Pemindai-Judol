# -*- coding: utf-8 -*-
"""
Auto-checker Lomba Website Desa OpenSID 2026.

Melakukan crawl ringan ke 38 URL peserta dan menghasilkan output/lomba/auto_check.json
yang berisi data terukur otomatis per desa:
  - http_ok          : apakah homepage merespons 200 OK
  - apbdes_2025      : apakah homepage memuat publikasi/referensi APBDes 2025
  - apbdes_2026      : apakah homepage memuat publikasi/referensi APBDes 2026
  - artikel_terakhir : tanggal artikel terbaru (berita)
  - artikel_30hari   : jumlah artikel dalam 30 hari terakhir (kuantitas berita)
  - surat_2026       : jumlah surat tercetak 2026 (dasar Layanan Administrasi)
  - opensid_version  : versi OpenSID terdeteksi
  - checked_at       : waktu crawling

Skor otomatis DIPEROLEH dari data ini di gen_lomba_dashboard.py
(proposional terhadap nilai tertinggi per komponen).
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests

sys.path.insert(0, r"C:\Users\komin\Documents\Default Project\desa-opensid-monitor")
os.chdir(r"C:\Users\komin\Documents\Default Project\desa-opensid-monitor")
requests.packages.urllib3.disable_warnings()

from src.reporter import _load_surat_data  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
PESERTA_PATH = os.path.join(BASE, "output", "lomba", "peserta.json")
AUTO_PATH = os.path.join(BASE, "output", "lomba", "auto_check.json")
RESULTS_DESA_PATH = os.path.join(BASE, "output", "desa", "results_desa.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}
TIMEOUT = 20
THIRTY_DAYS = 30


def _fetch(url):
    try:
        r = requests.get(url, timeout=TIMEOUT, headers=HEADERS,
                         allow_redirects=True, verify=False)
        return r
    except Exception:
        return None


def _parse_date(s):
    """Parse ISO/Indonesia date loosely."""
    if not s:
        return None
    s = str(s).strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return datetime(*map(int, m.groups()))
        except ValueError:
            return None
    return None


def _article_count_30d(html, url):
    """Estimate jumlah artikel 30 hari terakhir dari homepage + feed."""
    if not html:
        return 0
    # Artikel OpenSID biasanya '/artikel/YYYY/M/D/...' 
    now = datetime.now()
    cutoff = now - timedelta(days=THIRTY_DAYS)
    count = 0
    for m in re.finditer(r"/artikel/(\d{4})/(\d{1,2})/(\d{1,2})", html):
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if d >= cutoff and d <= now + timedelta(days=1):
                count += 1
        except ValueError:
            continue
    return count


def _last_article_date(html):
    if not html:
        return None
    dates = []
    for m in re.finditer(r"/artikel/(\d{4})/(\d{1,2})/(\d{1,2})", html):
        try:
            dates.append(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    return max(dates) if dates else None


def _has_apbdes(html, year):
    if not html:
        return False
    low = html.lower()
    # 'apbdes 2025', 'apbdes-2025', 'apbdes tahun 2025', 'apbdes_2025'
    if re.search(r"apbdes[^0-9]{0,4}" + str(year), low):
        return True
    if re.search(r"apbdes[-_]" + str(year), low):
        return True
    return "realisasi apbdes " + str(year) in low


def load_results_desa():
    try:
        with open(RESULTS_DESA_PATH, encoding="utf-8") as f:
            data = json.load(f)
        byurl = {r["url"].rstrip("/").lower(): r for r in data.get("results", [])}
        return byurl
    except Exception:
        return {}


def main():
    with open(PESERTA_PATH, encoding="utf-8") as f:
        peserta = json.load(f)

    # Surat 2026 per desa
    total_map, monthly_map, _ = _load_surat_data()
    def surat_2026(name):
        mo = monthly_map.get(name, {})
        return sum(v for k, v in mo.items() if k.startswith("2026-"))

    res_by_url = load_results_desa()

    output = {}
    for p in peserta:
        desa = p["desa"]
        url = p["url"]
        key = url.rstrip("/").lower()
        rec = {
            "no": p["no"],
            "desa": desa,
            "kecamatan": p["kecamatan"],
            "url": url,
            "http_ok": False,
            "http_status": None,
            "apbdes_2025": False,
            "apbdes_2026": False,
            "artikel_30hari": 0,
            "artikel_terakhir": None,
            "surat_2026": 0,
            "opensid_version": None,
            "checked_at": None,
        }

        # enrich dari snapshot hasil scan (http_status, versi, berita)
        snap = res_by_url.get(key)
        if snap:
            rec["http_status"] = snap.get("http_status")
            rec["http_ok"] = snap.get("http_status") == 200
            rec["opensid_version"] = snap.get("opensid_version")
            if snap.get("last_post"):
                rec["berita_terakhir"] = snap["last_post"].get("date") or \
                    snap["last_post"].get("href") or ""
        # surat 2026 dari maps (coba cocokkan nama snapshot via nama hasil)
        if snap:
            rec["surat_2026"] = surat_2026(snap["name"]) or 0

        # Live fetch untuk hasil akurat
        resp = _fetch(url)
        if resp is not None:
            rec["http_status"] = resp.status_code
            rec["http_ok"] = resp.status_code == 200
            html = resp.text if rec["http_ok"] else ""
            rec["apbdes_2025"] = _has_apbdes(html, 2025)
            rec["apbdes_2026"] = _has_apbdes(html, 2026)
            rec["artikel_30hari"] = _article_count_30d(html, url)
            lad = _last_article_date(html)
            if lad:
                rec["artikel_terakhir"] = lad.strftime("%Y-%m-%d")

        rec["checked_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output[key] = rec
        print(f"{p['no']:>2}. {desa:22s} http={rec['http_status']} "
              f"apbdes25={rec['apbdes_2025']} apbdes26={rec['apbdes_2026']} "
              f"art30={rec['artikel_30hari']} surat26={rec['surat_2026']}")

    os.makedirs(os.path.dirname(AUTO_PATH), exist_ok=True)
    with open(AUTO_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nWritten:", AUTO_PATH)


if __name__ == "__main__":
    main()
