# -*- coding: utf-8 -*-
"""
Modul Reporter:
- Menampilkan tabel dashboard di console (CLI) sesuai kolom spesifikasi:
  [Status Indicator] | [Nama Desa] | [URL Website] | [Judul Postingan
  Terakhir] | [Tanggal Publish] | [Keterangan / Indikasi Spam]
- Urgent Flagging & Re-Ordering: website terdeteksi judi/spam diberi tanda
  merah (HIGH PRIORITY CRITICAL) dan diposisikan OTOMATIS DI PALING ATAS.
- Mode interaktif: filter / halaman hasil.
- Menghasilkan dashboard HTML (output/dashboard.html), snapshot JSON
  (output/last_scan.json), dan CSV (output/last_scan.csv).
"""

import csv
import html as html_lib
import json
import os
import re as _re
from collections import Counter
from datetime import datetime

from colorama import Back, Fore, Style

from config.profiles import get_profile
from data.targets import KECAMATAN_ORDER, TARGETS
from data.targets_opd import CATEGORY_ORDER

STATUS_ORDER = {"DETECTED": 0, "AMAN": 1, "OFFLINE": 2}

_RE_ANSI = _re.compile(r"\x1b\[[0-9;]*m")

BULAN_MAP_NUM_TO_NAME = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}


def _normalize_desa_name(name):
    """Normalize desa name by stripping suffixes like ' Ngawi', ' Ngawi' etc."""
    n = name.strip()
    for suffix in [" Ngawi", " Ngawi"]:
        if n.endswith(suffix) and len(n) > len(suffix):
            n = n[:-len(suffix)]
    return n


def _load_surat_data():
    """Load surat tercetak data from JSON.

    Returns (total_map, monthly_map, available_months):
    - total_map: {desa_name: total_surat_count}
    - monthly_map: {desa_name: {"2024-03": 5, ...}}
    - available_months: sorted list of "YYYY-MM" strings with data
    """
    path = os.path.join(os.path.dirname(__file__), "..", "output", "desa", "surat_tercetak.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        total_map = {}
        monthly_map = {}
        all_months = set()
        for r in data.get("results", []):
            name = r["name"]
            total_map[name] = r.get("surat_tercetak")
            mo = r.get("monthly", {})
            if mo:
                monthly_map[name] = mo
                all_months.update(mo.keys())
        # Build reverse lookup: normalized_name -> original_name
        # So "Ngawi Ngawi" (dashboard name) can look up "Ngawi" (scraper name)
        reverse_total = {}
        reverse_monthly = {}
        for name, val in total_map.items():
            norm = _normalize_desa_name(name)
            if norm != name:
                reverse_total[name] = val  # "Ngawi" -> 593 (already there)
                # Also add the dashboard-style name as an alias
                # Find the original that strips to this norm
            # Build a map from stripped -> original
        # Simpler approach: for each original key, add a mapping
        # from "X Ngawi" -> same value as "X"
        for name in list(total_map.keys()):
            norm = _normalize_desa_name(name)
            if norm != name and norm not in total_map:
                total_map[norm] = total_map[name]
            if norm != name:
                # Dashboard uses "X Ngawi", scraper has "X"
                # Make "X Ngawi" resolve to same value
                dashboard_name = name + " Ngawi" if not name.endswith(" Ngawi") else name
        # Actually, simplest: just add entries for names with " Ngawi" suffix
        orig_keys = list(total_map.keys())
        for name in orig_keys:
            if not name.endswith(" Ngawi"):
                aliased = name + " Ngawi"
                if aliased not in total_map:
                    total_map[aliased] = total_map[name]
        orig_monthly_keys = list(monthly_map.keys())
        for name in orig_monthly_keys:
            if not name.endswith(" Ngawi"):
                aliased = name + " Ngawi"
                if aliased not in monthly_map:
                    monthly_map[aliased] = monthly_map[name]

        # Additional aliases: hyphen <-> space, merged names
        _extra_aliases = {
            "Bangunrejo Lor": "Bangunrejolor",
            "Genmarang": "Gemarang",
            "Tambakromo-geneng": "Tambakromo Geneng",
            "Tambakromo-padas": "Tambakromo Padas",
            "Kauman-Sine": "Kauman Sine",
            "Kauman-Widodaren": "Kauman Widodaren",
            "Sidorejo-Karangjati": "Sidorejo Karangjati",
            "Sidorejo-Kendal": "Sidorejo Kendal",
            "Waruktengah": "Waruk Tengah",
            "Simo Kwadungan": "Simo-Kwadungan",
            "Simo Kendal": "Simo-Kendal",
            "Karangtengahprandon": "Karangtengah Prandon",
            "Babadan Pangkur": "Babadan",
        }
        for key, alias in _extra_aliases.items():
            if key in total_map and alias not in total_map:
                total_map[alias] = total_map[key]
            elif alias in total_map and key not in total_map:
                total_map[key] = total_map[alias]
            if key in monthly_map and alias not in monthly_map:
                monthly_map[alias] = monthly_map[key]
            elif alias in monthly_map and key not in monthly_map:
                monthly_map[key] = monthly_map[alias]

        # Normalize: for each name with hyphen, add space variant and vice versa
        for name in list(total_map.keys()):
            if "-" in name:
                space_name = name.replace("-", " ")
                if space_name not in total_map:
                    total_map[space_name] = total_map[name]
                if name in monthly_map and space_name not in monthly_map:
                    monthly_map[space_name] = monthly_map[name]
            elif " " in name:
                hyphen_name = name.replace(" ", "-")
                if hyphen_name not in total_map:
                    total_map[hyphen_name] = total_map[name]
                if name in monthly_map and hyphen_name not in monthly_map:
                    monthly_map[hyphen_name] = monthly_map[name]
        return total_map, monthly_map, sorted(all_months)
    except Exception:
        return {}, {}, []

STATUS_LABEL = {
    "DETECTED": "TERINDIKASI JUDI/SPAM",
    "AMAN": "AMAN",
    "OFFLINE": "OFFLINE / TIMEOUT",
}

STATUS_ICON = {
    "DETECTED": "[!]",
    "AMAN": "[ok]",
    "OFFLINE": "[--]",
}


def sort_results(results):
    """Urutan DEFAULT monitor: postingan terbaru di paling atas (untuk OPD
    maupun desa), lalu abjad nama. Status hanya menjadi tiebreaker ketika
    tanggal tidak tersedia."""
    def _status_rank(r):
        if r["status"] == "DETECTED" and r.get("critical"):
            return 0
        if r["status"] == "DETECTED":
            return 1
        if r["status"] == "AMAN":
            return 2
        if r["status"] == "OFFLINE":
            return 3
        return 4

    def _kw_count(r):
        return len(r.get("keywords") or []) if r["status"] == "DETECTED" else 0

    def _date_key(r):
        last = r.get("last_post")
        dt = last["date"] if last and last.get("date") else None
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        if dt:
            return str(dt)
        return ""

    def _sort_key(r):
        d = _date_key(r)
        # reverse=True (desc): grup ber-tanggal (1) di atas yang tanpa tanggal
        # (0); dalam grup ber-tanggal, tanggal terbaru naik paling atas,
        # lalu status (critical/detected > aman > offline), keyword terbanyak,
        # abjad nama.
        return (1 if d else 0, d, -_status_rank(r), _kw_count(r),
                r["name"].lower())

    return sorted(results, key=_sort_key, reverse=True)


def _fmt_date(d):
    if not d:
        return "-"
    if isinstance(d, datetime):
        return d.strftime("%d/%m/%Y")
    return str(d)


def summarize(results):
    return {
        "total": len(results),
        "detected": sum(1 for r in results if r["status"] == "DETECTED"),
        "safe": sum(1 for r in results if r["status"] == "AMAN"),
        "offline": sum(1 for r in results if r["status"] == "OFFLINE"),
        "critical": sum(1 for r in results if r.get("critical")),
    }


def _keterangan(r):
    if r["status"] == "OFFLINE":
        return r.get("error") or STATUS_LABEL["OFFLINE"]
    if r["status"] == "DETECTED":
        parts = []
        for m in r["keywords"][:5]:
            src = m.get("source", "")
            if m.get("page"):
                src = m["page"].rstrip("/").rsplit("/", 1)[-1]
            parts.append("%s (%s)" % (m["keyword"], src))
        if len(r["keywords"]) > 5:
            parts.append("+%d lainnya" % (len(r["keywords"]) - 5))
        return "; ".join(parts)
    return "Tidak ditemukan indikasi"


def print_header(profile=None):
    p = get_profile(profile)
    print()
    print(Style.BRIGHT + "=" * 78)
    print("  PEMANTAU WEBSITE - INDIKASI KONTEN JUDI ONLINE")
    print("  %s" % p["subject"])
    print("  %d Target %s" % (len(p["targets"]), p["count_label"]))
    print("=" * 78 + Style.RESET_ALL)
    print()


def _status_cell(status, critical=False):
    if status == "DETECTED":
        label = STATUS_LABEL[status]
        if critical:
            label = "CRITICAL " + label
        return Back.RED + Fore.WHITE + " " + label + " " + Style.RESET_ALL
    if status == "AMAN":
        return Fore.GREEN + STATUS_LABEL[status] + Style.RESET_ALL
    return Fore.YELLOW + STATUS_LABEL[status] + Style.RESET_ALL


def _print_table(results, profile=None):
    p = get_profile(profile)
    headers = [
        "STATUS",
        p["col_label"].upper(),
        "URL WEBSITE",
        "JUDUL POSTINGAN TERAKHIR",
        "TANGGAL",
        "KETERANGAN / INDIKASI SPAM",
    ]
    rows = []
    for r in results:
        judul = ""
        if r["last_post"] and r["last_post"].get("title"):
            judul = r["last_post"]["title"]
        elif r.get("title"):
            judul = r["title"]
        rows.append([
            _status_cell(r["status"], r.get("critical")),
            r["name"],
            r["url"],
            judul[:70],
            _fmt_date(r["last_post"]["date"] if r["last_post"] else None),
            _keterangan(r)[:60],
        ])

    widths = []
    for c in range(len(headers)):
        max_len = len(headers[c])
        for row in rows:
            plain = re_strip(row[c])
            max_len = max(max_len, len(plain))
        widths.append(min(max_len, 60))

    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    print(line)
    print("|" + "|".join(
        " " + headers[i].ljust(widths[i]) + " "
        for i in range(len(headers))
    ) + "|")
    print(line)
    for idx, row in enumerate(rows):
        cells = []
        for i, cell in enumerate(row):
            cells.append(" " + pad_cell(cell, widths[i]) + " ")
        row_str = "|" + "|".join(cells) + "|"
        if results[idx]["status"] == "DETECTED":
            print(Back.RED + Fore.WHITE + row_str + Style.RESET_ALL)
        else:
            print(row_str)
    print(line)


def print_table(results, profile=None):
    return _print_table(results, profile=profile)


def re_strip(text):
    return _RE_ANSI.sub("", str(text or ""))


def pad_cell(cell, width):
    """Pad sel sambil memperhitungkan panjang teks tanpa kode ANSI."""
    s = str(cell or "")
    plain = re_strip(s)
    return s + " " * max(0, width - len(plain))


def print_summary(results):
    s = summarize(results)
    print()
    print(Style.BRIGHT + "=== RINGKASAN ===" + Style.RESET_ALL)
    print("Total target          : %d" % s["total"])
    if s["detected"]:
        print(Back.RED + Fore.WHITE +
              "TERINDIKASI JUDI/SPAM: %d  <-- TINDAK LANJUT SEGERA!"
              % s["detected"] + Style.RESET_ALL)
    else:
        print(Fore.GREEN + "TERINDIKASI JUDI/SPAM: 0" + Style.RESET_ALL)
    if s.get("critical"):
        print(Back.MAGENTA + Fore.WHITE +
              "SPAM ASING / HACK     : %d  <-- CRITICAL! TINDAK LANJUT SEGERA!"
              % s["critical"] + Style.RESET_ALL)
    print(Fore.GREEN + "AMAN                  : %d" % s["safe"] + Style.RESET_ALL)
    print(Fore.YELLOW + "OFFLINE / TIMEOUT     : %d" % s["offline"] + Style.RESET_ALL)
    print()


def interactive_browse(results, profile=None):
    """Jelajahi hasil scan secara interaktif (filter per status)."""
    filters = {
        "a": ("Semua", None),
        "d": ("Terindikasi Judi/Spam", "DETECTED"),
        "s": ("Aman", "AMAN"),
        "o": ("Offline/Timeout", "OFFLINE"),
    }
    current = "a"
    while True:
        status = filters[current][1]
        sub = results if status is None else [r for r in results if r["status"] == status]
        print(Style.BRIGHT + "\n>>> FILTER: %s (%d hasil)"
              % (filters[current][0], len(sub)) + Style.RESET_ALL)
        _print_table(sub, profile=profile)
        print_summary(sub)
        choice = input(
            "[a] Semua  [d] Terindikasi  [s] Aman  [o] Offline  [q] Keluar > "
        ).strip().lower()
        if choice == "q" or choice == "":
            break
        if choice in filters:
            current = choice


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; background: #eef2f6; color: #1f2937; }
header { background-image: url('/assets/bg-header.svg'); background-size: cover; background-position: center; color: #1E293B; padding: 26px 32px 20px; position: relative; }
.logo-wrap { position: absolute; top: 16px; right: 24px; text-align: center; max-width: 220px; }
.logo-wrap.left { left: 18px; right: auto; top: 18px; max-width: 90px; }
.logo-wrap img { height: 58px; display: block; margin: 0 auto; filter: drop-shadow(0 1px 2px rgba(0,0,0,.25)); }
.logo-wrap.left img { height: 58px; }
.logo-caption { font-size: 11px; color: #1E293B; margin-top: 6px; line-height: 1.35; font-weight: 600; }
@media (max-width: 760px) { .logo-wrap { position: static; margin: 14px auto 0; } .logo-wrap.left { margin-top: 0; } header h1, header p { padding-left: 0; } }
header h1 { margin: 0 0 4px; font-size: 23px; padding-left: 76px; color: #0F172A; }
header p { margin: 4px 0 0; font-size: 13px; padding-left: 76px; color: #334155; }
.stats { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 18px; }
.stat { background: rgba(255,255,255,0.85); backdrop-filter: blur(4px); border: 1px solid rgba(255,255,255,.6); border-radius: 10px; padding: 12px 20px; min-width: 140px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.stat .num { font-size: 30px; font-weight: 800; color: #1E293B; }
.stat .lbl { font-size: 12px; color: #475569; }
.wrap { padding: 22px 28px 40px; }
.alarm { display: none; background: #dc3545; color: #fff; padding: 14px 18px; border-radius: 10px; font-weight: 700; margin-bottom: 18px; }
.alarm.show { display: block; }
.toolbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; }
.toolbar input[type=text] { flex: 1; min-width: 220px; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
.toolbar .fbtn { padding: 9px 16px; border: 1px solid #cbd5e1; background: #fff; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 13px; }
.toolbar .fbtn.active { background: #16679a; color: #fff; border-color: #16679a; }
select#kec-filter, select#month-filter { padding: 6px 12px; border-radius: 8px; border: 1px solid #d1d5db; font-size: 14px; font-weight: 600; color: #1e293b; background: #fff; cursor: pointer; }
.toolbar-label { font-weight: 700; font-size: 13px; color: #334155; margin-right: 4px; }
.scanbar { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; background: #fff; border: 1px solid #cbd5e1; border-radius: 10px; padding: 12px 16px; margin-bottom: 14px; box-shadow: 0 1px 4px rgba(15,61,94,.08); }
#btn-scan { background: linear-gradient(135deg, #16a34a, #15803d); color: #fff; border: 0; border-radius: 8px; padding: 12px 22px; font-size: 15px; font-weight: 800; cursor: pointer; }
#btn-scan:hover { filter: brightness(1.08); }
#btn-scan:disabled { background: #94a3b8; cursor: wait; }
.scaninfo { font-size: 13px; color: #334155; display: flex; flex-direction: column; gap: 3px; }
.scaninfo b { color: #111827; }
#scan-state.scanning { color: #16a34a; font-weight: 800; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(15,61,94,.12); }
th, td { padding: 11px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; font-size: 13px; vertical-align: top; }
th { background: #f8fafc; color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: .4px; white-space: nowrap; }
tbody tr:hover { background: #f8fafc; }
tr.row-danger { background: #fde8e8; }
tr.row-danger:hover { background: #fcd7d7; }
tr.row-spam { background: #f5e8ff; }
tr.row-spam:hover { background: #ecd9ff; }
tr.row-repeated { background: #fff4e0; }
tr.row-repeated:hover { background: #ffe9c7; }
.badge.repeated { background: #d97706; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 800; color: #fff; white-space: nowrap; }
.badge.detected { background: #dc3545; }
.badge.safe { background: #198754; }
.badge.offline { background: #b7791f; }
.badge.spam { background: #7c3aed; }
.badge.spam-comment { background: #f97316; }
.name { font-weight: 700; }
.tag { display: inline-block; font-size: 10px; background: #e2e8f0; color: #475569; border-radius: 4px; padding: 1px 6px; margin-top: 3px; }
.url { color: #16679a; word-break: break-all; }
.ver { display: inline-block; font-size: 11px; border-radius: 4px; padding: 2px 7px; font-weight: 600; }
.ver-uptodate { background: #dcfce7; color: #166534; }
.ver-below { background: #fef3c7; color: #92400e; }
.ver-unknown { background: #f1f5f9; color: #64748b; }
.ver-filter-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ver-filter-bar select { padding: 6px 12px; border-radius: 8px; border: 1px solid #cbd5e1; font-size: 13px; font-weight: 600; }
.stat.ver-stat { cursor: pointer; border-left: 4px solid #f97316; }
.stat.ver-stat:hover { background: #fff7ed; }
.post-title { font-weight: 600; max-width: 320px; }
.chip { display: inline-block; background: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; border-radius: 6px; padding: 2px 8px; margin: 2px 2px 2px 0; font-size: 11px; }
.chip em { font-style: normal; font-weight: 700; }
.chip-spam { background: #f3e8ff; color: #6b21a8; border-color: #e9d5ff; }
.chip-repeated { background: #fef3c7; color: #92400e; border-color: #fde68a; }
.chip-comment { background: #dbeafe; color: #1e40af; border-color: #bfdbfe; }
.chip-action { background: #dcfce7; color: #166534; border-color: #bbf7d0; text-decoration: none; cursor: pointer; }
.chip-action:hover { background: #bbf7d0; }
.btn-link { display: inline-block; padding: 4px 12px; border-radius: 6px; background: #16679a; color: #fff !important; text-decoration: none; font-size: 12px; font-weight: 700; white-space: nowrap; }
.btn-link:hover { background: #0f4d75; }
footer { text-align: center; color: #94a3b8; font-size: 12px; padding: 18px; }
.name-link { cursor: pointer; color: #1e40af; text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 2px; }
.name-link:hover { color: #7c3aed; }
.modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.45); z-index: 9999; justify-content: center; align-items: center; }
.modal-overlay.open { display: flex; }
.modal-box { background: #fff; border-radius: 14px; width: 94vw; max-width: 720px; max-height: 88vh; overflow-y: auto; box-shadow: 0 12px 40px rgba(0,0,0,.25); padding: 0; }
.modal-header { background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff; padding: 18px 24px; display: flex; justify-content: space-between; align-items: center; border-radius: 14px 14px 0 0; }
.modal-header h3 { margin: 0; font-size: 17px; font-weight: 800; }
.modal-close { background: rgba(255,255,255,.2); border: 0; color: #fff; font-size: 22px; width: 36px; height: 36px; border-radius: 50%; cursor: pointer; font-weight: 800; line-height: 1; }
.modal-close:hover { background: rgba(255,255,255,.35); }
.modal-body { padding: 20px 24px 24px; }
.modal-year-row { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
.modal-year-row label { font-weight: 700; font-size: 13px; color: #475569; }
.modal-year-row select { padding: 7px 14px; border-radius: 8px; border: 1px solid #cbd5e1; font-size: 14px; font-weight: 600; }
.modal-total-row { display: flex; gap: 20px; margin-bottom: 18px; flex-wrap: wrap; }
.modal-stat { background: #f1f5f9; border-radius: 10px; padding: 10px 18px; text-align: center; min-width: 120px; }
.modal-stat .val { font-size: 26px; font-weight: 800; color: #1e40af; }
.modal-stat .lbl { font-size: 11px; color: #64748b; margin-top: 2px; }
.monthly-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
.month-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 10px; text-align: center; transition: box-shadow .15s; }
.month-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.month-card .mname { font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: .3px; }
.month-card .mval { font-size: 22px; font-weight: 800; margin-top: 4px; }
.month-card .mval.has-data { color: #16a34a; }
.month-card .mval.no-data { color: #cbd5e1; }
.chart-container { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-top: 8px; }
.chart-title { font-size: 13px; font-weight: 700; color: #475569; margin-bottom: 10px; }
.chart-bars { display: flex; align-items: flex-end; gap: 6px; height: 120px; }
.chart-bar-wrap { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
.chart-bar { width: 100%; max-width: 36px; border-radius: 4px 4px 0 0; background: #4f46e5; min-height: 2px; transition: height .3s; }
.chart-bar:hover { background: #7c3aed; }
.chart-bar-label { font-size: 9px; color: #94a3b8; margin-top: 4px; writing-mode: horizontal-tb; }
.chart-bar-val { font-size: 9px; font-weight: 700; color: #475569; margin-bottom: 2px; }
@media (max-width: 520px) { .monthly-grid { grid-template-columns: repeat(3, 1fr); } }
"""


def _esc(s):
    return html_lib.escape(str(s if s is not None else ""))


def _status_badge_html(status, critical=False, has_spam_comments=False, repeated_posts=None):
    if status == "DETECTED" and critical:
        return '<span class="badge spam">CRITICAL SPAM / HACK</span>'
    if status == "DETECTED" and repeated_posts:
        return '<span class="badge repeated">POSTINGAN BERULANG (SPAM)</span>'
    if status == "DETECTED":
        return '<span class="badge detected">TERINDIKASI JUDI/SPAM</span>'
    if status == "AMAN" and has_spam_comments:
        return '<span class="badge spam-comment">AMAN + SPAM KOMENTAR</span>'
    if status == "AMAN":
        return '<span class="badge safe">AMAN</span>'
    return '<span class="badge offline">OFFLINE / TIMEOUT</span>'


def _keterangan_html(r):
    if r["status"] == "OFFLINE":
        return _esc(r.get("error") or STATUS_LABEL["OFFLINE"])
    if r["status"] == "DETECTED":
        chips = []
        repeated_seen = False
        for m in r["keywords"][:25]:
            if m.get("repeated") and not repeated_seen:
                # Pindahkan info postingan berulang ke blok khusus di bawah.
                repeated_seen = True
                continue
            if m.get("repeated"):
                continue
            cls = "chip chip-spam" if (m.get("foreign") or m.get("cyber")) else "chip"
            src = m.get("source", "")
            if m.get("page"):
                src = m["page"].rstrip("/").rsplit("/", 1)[-1]
            chips.append('<span class="%s"><em>%s</em> (%s)</span>'
                         % (cls, _esc(m["keyword"]), _esc(src)))
        if r.get("repeated_posts"):
            reps = ['<span class="chip chip-repeated"><em>&#128260; %d Postingan Berulang (judul sama)</em></span>'
                    % len(r["repeated_posts"])]
            for d in r["repeated_posts"][:3]:
                reps.append('<span class="chip chip-repeated"><em>%s</em> x%d</span>'
                            % (_esc(d["title"][:60]), d["count"]))
            if len(r["repeated_posts"]) > 3:
                reps.append('<span class="chip">+%d judul lainnya</span>'
                            % (len(r["repeated_posts"]) - 3))
            chips.extend(reps)
        return "".join(chips)
    # Cek komentar spam (untuk status AMAN)
    spam_comments = r.get("spam_comments", [])
    comment_info = r.get("comment_system") or {}
    if spam_comments:
        chips = ['<span class="chip chip-spam"><em>&#9888; %d Komentar Spam</em></span>'
                 % len(spam_comments)]
        for c in spam_comments[:5]:
            sample = _esc(c["text"][:80])
            chips.append('<span class="chip"><em>%s</em></span>' % sample)
        if len(spam_comments) > 5:
            chips.append('<span class="chip">+%d lainnya</span>' % (len(spam_comments) - 5))
        if comment_info.get("comment_admin_url"):
            chips.append('<a href="%s" target="_blank" class="chip chip-action">&#128221; Hapus di Admin</a>'
                         % _esc(comment_info["comment_admin_url"]))
        return "".join(chips)
    # Tampilkan info sistem komentar aktif (hanya untuk non-OpenSID)
    if comment_info.get("has_comments") and comment_info.get("system") != "opensid":
        system = comment_info.get("system", "")
        admin_url = comment_info.get("comment_admin_url", "")
        label = "WordPress + Akismet" if comment_info.get("akismet") else system.title()
        chip = '<span class="chip chip-comment"><em>&#128172; Komentar Aktif (%s)</em></span>' % _esc(label)
        if admin_url:
            chip += ' <a href="%s" target="_blank" class="chip chip-action">&#128221; Kelola Komentar</a>' % _esc(admin_url)
        return chip
    return '<span style="color:#198754;font-weight:700;">BERSIH</span>'


def render_html(results, meta, auto_refresh=0, profile=None):
    p = get_profile(profile)
    by_kecamatan = p["filter_mode"] == "kecamatan"
    group_col = "Kecamatan" if by_kecamatan else "Kategori"
    refresh_meta = (
        '<meta http-equiv="refresh" content="%d">' % auto_refresh if auto_refresh else ""
    )

    # Load surat tercetak data (total + monthly)
    surat_map, monthly_map, available_months = (_load_surat_data() if by_kecamatan else ({}, {}, []))
    total_surat = sum(v for v in surat_map.values() if v and v > 0) if surat_map else 0

    # Version counting for below-v2406 feature
    def _ver_tuple(v):
        if not v:
            return (0,)
        try:
            parts = str(v).split(".")
            return tuple(int(p) for p in parts)
        except Exception:
            return (0,)
    VER_THRESHOLD = (2406, 0, 0)
    ver_uptodate = sum(1 for r in results if r.get("opensid_version") and _ver_tuple(r["opensid_version"]) >= VER_THRESHOLD)
    ver_below = sum(1 for r in results if r.get("opensid_version") and _ver_tuple(r["opensid_version"]) < VER_THRESHOLD)
    ver_unknown = sum(1 for r in results if not r.get("opensid_version"))

    rows = []
    for idx, r in enumerate(results):
        last = r["last_post"]
        post_title = _esc(last["title"]) if last and last["title"] else \
            '<span style="color:#94a3b8;">-</span>'
        post_date = _esc(_fmt_date(last["date"])) if last else "-"
        last_date = last.get("date") if last else None
        date_sort = (last_date.strftime("%Y-%m-%dT%H:%M:%S")
                     if isinstance(last_date, datetime) else str(last_date)) \
            if last_date else ""
        link = r["url"]
        if last and last.get("href"):
            link = last["href"]
        group_val = r.get("kecamatan") if by_kecamatan else r.get("category")
        danger = " row-spam" if r.get("critical") else (
            " row-repeated" if (r.get("repeated_posts") and r["status"] == "DETECTED")
            else " row-danger" if r["status"] == "DETECTED" else ""
        )
        opensid_ver = r.get("opensid_version") or ""

        # Surat tercetak
        surat_count = surat_map.get(r["name"]) if surat_map else None
        mo_data = monthly_map.get(r["name"], {})
        mo_json = json.dumps(mo_data, ensure_ascii=False) if mo_data else "{}"
        if surat_count is not None:
            surat_td = '<td style="font-weight:700;color:#1e40af;" class="surat-total">%d</td>' % surat_count if surat_count > 0 \
                else '<td style="color:#94a3b8;" class="surat-total">0</td>'
        else:
            surat_td = '<td style="color:#94a3b8;" class="surat-total">-</td>' if surat_map else ''

        ver_td = ('<td data-ver="%s"><span class="ver ver-uptodate">v%s</span></td>' % (_esc(opensid_ver), _esc(opensid_ver))) if opensid_ver and _ver_tuple(opensid_ver) >= VER_THRESHOLD \
            else ('<td data-ver="%s"><span class="ver ver-below">v%s</span></td>' % (_esc(opensid_ver), _esc(opensid_ver))) if opensid_ver \
            else ('<td data-ver=""><span class="ver ver-unknown">-</span></td>' if by_kecamatan else '<td data-ver=""></td>')

        rows.append(
            "<tr class=\"%s\" data-status=\"%s\" data-group=\"%s\" "
            "data-date=\"%s\" data-index=\"%d\" data-monthly='%s'>"
            "<td>%s</td>"
            "<td>%s<span class=\"tag\">%s</span></td>"
            "<td>%s</td>"
            "<td class=\"url\">%s</td>"
            "%s"
            "%s"
            "<td class=\"post-title\">%s</td>"
            "<td>%s</td>"
            "<td>%s</td>"
            "<td><a class=\"btn-link\" href=\"%s\" target=\"_blank\" rel=\"noopener\">Buka &rarr;</a></td>"
            "</tr>"
            % (
                danger,
                r["status"],
                _esc(group_val or ""),
                _esc(date_sort),
                idx,
                _esc(mo_json),
                _status_badge_html(r["status"], r.get("critical"),
                                  bool(r.get("spam_comments")),
                                  r.get("repeated_posts")),
                ('<span class="name name-link" onclick="openSuratModal(this.closest(\'tr\'))">%s</span>' % _esc(r["name"])) if surat_map else ('<span class="name">%s</span>' % _esc(r["name"])),
                _esc(r["category"]),
                _esc(group_val or "-"),
                _esc(r["url"]),
                ver_td,
                surat_td,
                post_title,
                post_date,
                _keterangan_html(r),
                _esc(link),
            )
        )

    body_rows = "\n".join(rows)

    if by_kecamatan:
        groups = KECAMATAN_ORDER
        group_all_label = "Semua Kecamatan"
    else:
        groups = CATEGORY_ORDER
        group_all_label = "Semua Kategori"
    group_counts = Counter(r.get("category") for r in results)

    if by_kecamatan:
        group_toolbar = (
            '<select id="kec-filter" onchange="setGroup(this.value)">'
            '<option value="all">%s</option>'
            '%s</select>'
            % (group_all_label,
               "".join('<option value="%s">%s</option>' % (g, g) for g in groups))
        )
    else:
        group_buttons = "".join(
            '<button class="fbtn" data-group="%s" onclick="setGroup(\'%s\')">%s%s</button>'
            % (g, g, g,
               (' <span class="cnt">(%d)</span>' % group_counts.get(g, 0)))
            for g in groups
        )
        group_toolbar = (
            '<button class="fbtn active" data-group="all" onclick="setGroup(\'all\')">'
            '&#127757; %s</button>%s' % (group_all_label, group_buttons)
        )

    date_toolbar = """
  <div class="toolbar">
    <span class="toolbar-label">&#128197; Tanggal Publish:</span>
    <button class="fbtn" data-datesort="desc" onclick="setDateSort('desc')">Terbaru</button>
    <button class="fbtn" data-datesort="asc" onclick="setDateSort('asc')">Terlama</button>
    <button class="fbtn active" data-datesort="none" onclick="setDateSort('none')">Urutan Default</button>
  </div>
""" + ("""
  <div class="toolbar">
    <span class="toolbar-label">&#128198; Filter Surat Tercetak per Bulan:</span>
    <select id="month-filter" onchange="setSuratMonthFilter(this.value)">
      <option value="all">Semua Bulan (Total Kumulatif)</option>
      %s
    </select>
    <span id="month-summary" style="font-size:12px;color:#475569;margin-left:8px;"></span>
  </div>
""" % "".join(
        '<option value="%s">%s %s</option>' % (
            m,
            BULAN_MAP_NUM_TO_NAME.get(int(m.split("-")[1]), ""),
            m.split("-")[0],
        )
        for m in available_months
    ) if by_kecamatan and available_months else "")

    scan_label = meta["scanned_at"].strftime("%d/%m/%Y %H:%M:%S")

    alarm_parts = []
    if meta["detected"]:
        alarm_parts.append(
            "&#9888; ALARM PRIORITAS TINGGI: %d target terindikasi konten "
            "judi online / spam." % meta["detected"]
        )
    if meta.get("critical"):
        alarm_parts.append(
            "&#9888; CRITICAL: %d target terindikasi Spam Injection / "
            "Hack Bahasa Asing." % meta["critical"]
        )
    alarm_block = (
        '<div class="alarm show">%s Segera tindak lanjuti!</div>'
        % " ".join(alarm_parts)
        if alarm_parts else '<div class="alarm"></div>'
    )

    clock_now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    scanbar = """
  <div class="scanbar">
    <button id="btn-scan" onclick="triggerScan()">&#128260;&#65039; SCAN SEKARANG (%d %s)</button>
    <div class="scaninfo">
      <div>&#128197; Scan terakhir: <b id="last-scan">%s</b></div>
      <div>&#128336; Mulai scan: <b id="scan-start">-</b> &bull; Jam: <b id="scan-clock">%s</b> &bull; Status: <b id="scan-state">siap</b></div>
    </div>
  </div>
""" % (meta["total"], p["count_label"], scan_label, clock_now)

    return """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/png" href="/logo_ngawi.png">
%s<title>Dashboard Pemantau - %s</title>
<style>%s</style>
</head>
<body>
<header>
  <h1>Pemantau Website - Indikasi Konten Judi Online / Spam</h1>
  <p>%s &bull; %d Target &bull; Update by date: <strong><span id="update-time">%s</span></strong></p>
  <div class="logo-wrap left">
    <img src="/logo_ngawi.png" alt="Logo Kabupaten Ngawi">
  </div>
  <div class="stats">
    <div class="stat"><div class="num">%d</div><div class="lbl">Total Target</div></div>
    <div class="stat"><div class="num" style="color:#ffb3b3;">%d</div><div class="lbl">TERINDIKASI JUDI/SPAM</div></div>
    <div class="stat"><div class="num" style="color:#b7ffce;">%d</div><div class="lbl">Aman</div></div>
    <div class="stat"><div class="num" style="color:#ffe2a1;">%d</div><div class="lbl">Offline / Timeout</div></div>
    %s
    %s
  </div>
  <div class="logo-wrap">
    <img src="/logo.png" alt="Logo Dinas Kominfo">
    <div class="logo-caption">Dinas Komunikasi Informatika Statistik dan Persandian Kabupaten Ngawi</div>
  </div>
</header>
<div class="wrap">
  %s
  %s
  <div class="toolbar">
    <input type="text" id="q" placeholder="Cari nama / URL / judul / kata kunci ..." oninput="applyFilter()">
    <button class="fbtn active" data-filter="all" onclick="setFilter('all')">Semua <span class="cnt">(%d)</span></button>
    <button class="fbtn" data-filter="DETECTED" onclick="setFilter('DETECTED')">&#128680; Terindikasi <span class="cnt" id="c-detected">(%d)</span></button>
    <button class="fbtn" data-filter="AMAN" onclick="setFilter('AMAN')">Aman <span class="cnt" id="c-safe">(%d)</span></button>
    <button class="fbtn" data-filter="OFFLINE" onclick="setFilter('OFFLINE')">Offline <span class="cnt" id="c-offline">(%d)</span></button>
  </div>
  <div class="toolbar group-toolbar">
    %s
  </div>
  %s
  <div class="toolbar ver-filter-bar">
    <span class="toolbar-label">&#128196; Filter Versi OpenSID:</span>
    <select id="ver-filter" onchange="setVerFilter(this.value)">
      <option value="all">Semua Versi</option>
      <option value="uptodate">v2406.0.0 (Terbaru)</option>
      <option value="below">Di Bawah v2406</option>
      <option value="unknown">Belum Terdeteksi</option>
    </select>
    <button class="fbtn" onclick="exportVerCSV()" style="margin-left:auto;">&#128229; Export CSV Upgrade</button>
  </div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>%s</th>
        <th>%s</th>
        <th>URL Website</th>
        %s
        %s
        <th>Judul Postingan Terakhir</th>
        <th>Tanggal Publish</th>
        <th>Keterangan / Indikasi Spam</th>
        <th>Aksi</th>
      </tr>
    </thead>
    <tbody>
%s
    </tbody>
  </table>
  <div class="modal-overlay" id="surat-modal" onclick="if(event.target===this)closeSuratModal()">
    <div class="modal-box">
      <div class="modal-header">
        <h3 id="modal-title">Rincian Surat Tercetak</h3>
        <button class="modal-close" onclick="closeSuratModal()">&times;</button>
      </div>
      <div class="modal-body">
        <div class="modal-year-row">
          <label>Tahun:</label>
          <select id="modal-year" onchange="renderModalYear()"></select>
        </div>
        <div class="modal-total-row">
          <div class="modal-stat"><div class="val" id="modal-total-widget">0</div><div class="lbl">Total Widget (Kumulatif)</div></div>
          <div class="modal-stat"><div class="val" id="modal-total-year" style="color:#16a34a;">0</div><div class="lbl">Total di Tahun Ini</div></div>
          <div class="modal-stat"><div class="val" id="modal-total-sum" style="color:#7c3aed;">0</div><div class="lbl">Jumlah dari Tabel</div></div>
        </div>
        <div class="monthly-grid" id="modal-grid"></div>
        <div class="chart-container">
          <div class="chart-title">Grafik Tren Cetak Surat per Bulan</div>
          <div class="chart-bars" id="modal-chart"></div>
        </div>
      </div>
    </div>
  </div>
</div>
<footer>Dihasilkan otomatis oleh Pemantau Website - Pemkab Ngawi &bull; %s</footer>
<script>
let currentFilter = 'all';
let currentGroup = 'all';
function setFilter(f) {
  currentFilter = f;
  document.querySelectorAll('.fbtn[data-filter]').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector('.fbtn[data-filter="' + f + '"]');
  if (btn) { btn.classList.add('active'); }
  applyFilter();
}
function setGroup(g) {
  currentGroup = g;
  document.querySelectorAll('.fbtn[data-group]').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector('.fbtn[data-group="' + g + '"]');
  if (btn) { btn.classList.add('active'); }
  applyFilter();
}
function applyFilter() {
  const q = (document.getElementById('q').value || '').toLowerCase();
  document.querySelectorAll('tbody tr').forEach(tr => {
    const st = tr.getAttribute('data-status');
    const gr = tr.getAttribute('data-group');
    const verTd = tr.querySelector('td[data-ver]');
    const ver = verTd ? verTd.getAttribute('data-ver') : '';
    const okStatus = currentFilter === 'all' || st === currentFilter;
    const okGroup = currentGroup === 'all' || gr === currentGroup;
    const okVer = currentVerFilter === 'all' || getVerStatus(ver) === currentVerFilter;
    const text = tr.textContent.toLowerCase();
    const okQ = !q || text.indexOf(q) !== -1;
    tr.style.display = (okStatus && okGroup && okVer && okQ) ? '' : 'none';
  });
}
let currentDateSort = 'none';
function setDateSort(s) {
  currentDateSort = s;
  document.querySelectorAll('.fbtn[data-datesort]').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector('.fbtn[data-datesort="' + s + '"]');
  if (btn) { btn.classList.add('active'); }
  const tbody = document.querySelector('tbody');
  const rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {
    const da = a.getAttribute('data-date') || '';
    const db = b.getAttribute('data-date') || '';
    const ia = parseInt(a.getAttribute('data-index'), 10);
    const ib = parseInt(b.getAttribute('data-index'), 10);
    if (s === 'none' || da === db) { return ia - ib; }
    if (!da) { return 1; }
    if (!db) { return -1; }
    return s === 'desc' ? (da < db ? 1 : -1) : (da < db ? -1 : 1);
  });
  rows.forEach(tr => tbody.appendChild(tr));
  applyFilter();
}
const MONTH_NAMES = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'];
let currentSuratMonth = 'all';
function setSuratMonthFilter(v) {
  currentSuratMonth = v;
  let totalSuratMonth = 0;
  document.querySelectorAll('tbody tr').forEach(tr => {
    const mo = JSON.parse(tr.getAttribute('data-monthly') || '{}');
    const suratTd = tr.querySelector('.surat-total');
    if (!suratTd) return;
    if (v === 'all') {
      const name = tr.querySelector('.name');
      const total = window.suratTotals && name ? window.suratTotals[name.textContent] : null;
      suratTd.textContent = total !== null && total !== undefined ? total : '-';
      suratTd.style.color = (total && total > 0) ? '#1e40af' : '#94a3b8';
      suratTd.style.fontWeight = (total && total > 0) ? '700' : '';
    } else {
      const count = mo[v] || 0;
      suratTd.textContent = count;
      if (count > 0) {
        suratTd.style.color = '#16a34a';
        suratTd.style.fontWeight = '700';
        totalSuratMonth += count;
      } else {
        suratTd.style.color = '#94a3b8';
        suratTd.style.fontWeight = '';
      }
    }
  });
  const summary = document.getElementById('month-summary');
  if (summary) {
    if (v === 'all') {
      summary.textContent = '';
    } else {
      const [y, m] = v.split('-');
      summary.textContent = 'Total ' + MONTH_NAMES[parseInt(m, 10) - 1] + ' ' + y + ': ' + totalSuratMonth + ' surat tercetak';
      summary.style.fontWeight = '700';
      summary.style.color = '#1e40af';
    }
  }
}
document.getElementById('c-detected').textContent = '(%d)';
document.getElementById('c-safe').textContent = '(%d)';
document.getElementById('c-offline').textContent = '(%d)';
function pad2(n) { return (n < 10 ? '0' : '') + n; }
function fmtDate(d) {
  return pad2(d.getDate()) + '/' + pad2(d.getMonth() + 1) + '/' + d.getFullYear() +
         ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
}
function nowStr() { return fmtDate(new Date()); }
const ut = document.getElementById('update-time');
const sc = document.getElementById('scan-clock');
const ss = document.getElementById('scan-state');
const btnScan = document.getElementById('btn-scan');
function tick() { const s = nowStr(); if (ut) { ut.textContent = s; } if (sc) { sc.textContent = s; } }
tick();
setInterval(tick, 1000);

function scanCount() {
  const m = btnScan.textContent.match(/\\((\\d+)/);
  return m ? m[1] : '';
}
function setScanningUI() {
  btnScan.disabled = true;
  btnScan.textContent = 'Memindai ' + scanCount() + ' website...';
  document.getElementById('scan-start').textContent = fmtDate(new Date());
  ss.textContent = 'memindai...';
  ss.classList.add('scanning');
}
function resetBtn() {
  btnScan.disabled = false;
  ss.textContent = 'siap';
  ss.classList.remove('scanning');
}
function waitScanDone() {
  const timer = setInterval(() => {
    fetch('/api/status').then(r => r.json()).then(s => {
      if (s.progress && s.progress.total) {
        btnScan.textContent = 'Memindai ' + s.progress.done + '/' + s.progress.total + ' website...';
        ss.textContent = 'memindai ' + s.progress.done + '/' + s.progress.total + ' website...';
      }
      if (!s.scanning) {
        clearInterval(timer);
        ss.textContent = 'selesai - memuat ulang...';
        setTimeout(() => { location.replace('/dashboard.html?noauto=1'); }, 500);
      }
    }).catch(() => {});
  }, 2000);
}
function triggerScan() {
  setScanningUI();
  fetch('/api/scan')
    .then(r => r.json())
    .then(d => {
      if (d.status === 'already_scanning') { ss.textContent = 'sudah memindai, menunggu...'; }
      waitScanDone();
    })
    .catch(() => { resetBtn(); ss.textContent = 'gagal memulai scan'; });
}
function initStatus() {
  fetch('/api/status').then(r => r.json()).then(s => {
    if (s.last_update) { document.getElementById('last-scan').textContent = s.last_update; }
    if (s.scanning) {
      setScanningUI();
      ss.textContent = 'sedang memindai otomatis...';
      if (s.progress && s.progress.total) {
        btnScan.textContent = 'Memindai ' + s.progress.done + '/' + s.progress.total + ' website...';
      }
      waitScanDone();
    }
  }).catch(() => {});
}
initStatus();
window.suratTotals = %s;
window.monthlyData = {};
let modalCurrentRow = null;
function openSuratModal(tr) {
  modalCurrentRow = tr;
  const name = (tr.querySelector('.name') || {}).textContent || '';
  const mo = JSON.parse(tr.getAttribute('data-monthly') || '{}');
  const totalWidget = window.suratTotals ? (window.suratTotals[name] || 0) : 0;
  document.getElementById('modal-title').textContent = 'Rincian Surat Tercetak \u2014 ' + name;
  const years = {};
  Object.keys(mo).forEach(ym => { if (ym.length >= 4) years[ym.substring(0, 4)] = true; });
  const yearList = Object.keys(years).sort().reverse();
  if (yearList.length === 0) {
    const now = new Date();
    yearList.push(String(now.getFullYear()));
  }
  const sel = document.getElementById('modal-year');
  sel.innerHTML = '';
  yearList.forEach(y => {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    sel.appendChild(opt);
  });
  window._modalMo = mo;
  window._modalWidgetTotal = totalWidget;
  renderModalYear();
  document.getElementById('surat-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeSuratModal() {
  document.getElementById('surat-modal').classList.remove('open');
  document.body.style.overflow = '';
  modalCurrentRow = null;
}
function renderModalYear() {
  const year = document.getElementById('modal-year').value;
  const mo = window._modalMo || {};
  const totalWidget = window._modalWidgetTotal || 0;
  let yearSum = 0;
  const grid = document.getElementById('modal-grid');
  const chart = document.getElementById('modal-chart');
  grid.innerHTML = '';
  chart.innerHTML = '';
  const monthVals = [];
  let maxVal = 1;
  for (let m = 1; m <= 12; m++) {
    const key = year + '-' + (m < 10 ? '0' + m : m);
    const count = mo[key] || 0;
    monthVals.push(count);
    if (count > maxVal) maxVal = count;
    yearSum += count;
    const card = document.createElement('div');
    card.className = 'month-card';
    card.innerHTML = '<div class="mname">' + MONTH_NAMES[m - 1] + '</div>'
      + '<div class="mval ' + (count > 0 ? 'has-data' : 'no-data') + '">' + count + '</div>';
    grid.appendChild(card);
  }
  document.getElementById('modal-total-widget').textContent = totalWidget;
  document.getElementById('modal-total-year').textContent = yearSum;
  document.getElementById('modal-total-sum').textContent = yearSum;
  for (let m = 0; m < 12; m++) {
    const pct = maxVal > 0 ? Math.max(2, (monthVals[m] / maxVal) * 100) : 2;
    const wrap = document.createElement('div');
    wrap.className = 'chart-bar-wrap';
    wrap.innerHTML = '<div class="chart-bar-val">' + (monthVals[m] > 0 ? monthVals[m] : '') + '</div>'
      + '<div class="chart-bar" style="height:' + pct + '%%"></div>'
      + '<div class="chart-bar-label">' + MONTH_NAMES[m].substring(0, 3) + '</div>';
    chart.appendChild(wrap);
  }
}
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeSuratModal(); });
let currentVerFilter = 'all';
function setVerFilter(v) {
  currentVerFilter = v;
  applyFilter();
}
function getVerStatus(ver) {
  if (!ver) return 'unknown';
  const parts = ver.split('.').map(Number);
  const threshold = [2406, 0, 0];
  for (let i = 0; i < 3; i++) {
    if ((parts[i] || 0) > threshold[i]) return 'uptodate';
    if ((parts[i] || 0) < threshold[i]) return 'below';
  }
  return 'uptodate';
}
function exportVerCSV() {
  var nl = String.fromCharCode(10);
  let csv = 'Nama Desa,Kecamatan,URL,Versi OpenSID,Surat 2026,Total Surat' + nl;
  document.querySelectorAll('tbody tr').forEach(tr => {
    const verTd = tr.querySelector('td[data-ver]');
    if (!verTd) return;
    const ver = verTd.getAttribute('data-ver');
    const st = tr.getAttribute('data-status');
    const name = (tr.querySelector('.name') || {}).textContent || '';
    const kec = tr.getAttribute('data-group') || '';
    const link = tr.querySelector('.url') ? tr.querySelector('.url').textContent : '';
    const suratTd = tr.querySelector('.surat-total');
    const surat = suratTd ? suratTd.textContent : '-';
    const mo = JSON.parse(tr.getAttribute('data-monthly') || '{}');
    const c2026 = Object.keys(mo).filter(k => k.startsWith('2026-')).reduce((s, k) => s + mo[k], 0);
    csv += '"' + name + '","' + kec + '","' + link + '","' + (ver || '-') + '",' + c2026 + ',' + surat + nl;
  });
  const blob = new Blob([csv], {type:'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'upgrade_opensid_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}
</script>
</body>
</html>
""" % (
        refresh_meta,
        _esc(p["subject"]),
        CSS,
        _esc(p["subject"]),
        meta["total"],
        scan_label,
        meta["total"],
        meta["detected"],
        meta["safe"],
        meta["offline"],
        '<div class="stat"><div class="num" style="color:#60a5fa;">%d</div><div class="lbl">Total Surat Tercetak</div></div>' % total_surat if surat_map else '',
        '<div class="stat ver-stat" onclick="document.getElementById(\'ver-filter\').value=\'below\';setVerFilter(\'below\')"><div class="num" style="color:#ea580c;">%d</div><div class="lbl">Versi Below v2406</div></div>' % ver_below if by_kecamatan else '',
        alarm_block,
        scanbar,
        meta["total"],
        meta["detected"],
        meta["safe"],
        meta["offline"],
        group_toolbar,
        date_toolbar,
        _esc(p["col_label"]),
        group_col,
        '<th>Versi OpenSID</th>' if by_kecamatan else '',
        '<th>Surat Tercetak</th>' if surat_map else '',
        body_rows,
        scan_label,
        meta["detected"],
        meta["safe"],
        meta["offline"],
        json.dumps(surat_map, ensure_ascii=False) if surat_map else "{}",
    )


def _json_result(r):
    return {
        "name": r["name"],
        "category": r["category"],
        "kecamatan": r.get("kecamatan", ""),
        "url": r["url"],
        "status": r["status"],
        "http_status": r["http_status"],
        "error": r["error"],
        "platform": r.get("platform"),
        "opensid_version": r.get("opensid_version"),
        "spam_comments": r.get("spam_comments", []),
        "comment_system": r.get("comment_system"),
        "title": r["title"],
        "last_post": r["last_post"],
        "repeated_posts": r.get("repeated_posts", []),
        "keywords": r["keywords"],
        "critical": r.get("critical", False),
        "foreign_scripts": r.get("foreign_scripts", []),
    }


def write_report(results, output_dir="output", auto_refresh=0, profile=None):
    p = get_profile(profile)
    by_kecamatan = p["filter_mode"] == "kecamatan"
    os.makedirs(output_dir, exist_ok=True)
    results_sorted = sort_results(results)
    meta = summarize(results_sorted)
    meta["scanned_at"] = datetime.now()

    html_path = os.path.join(output_dir, p["html_name"])
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(results_sorted, meta, auto_refresh=auto_refresh, profile=p))

    snapshot = {
        "scanned_at": meta["scanned_at"].isoformat(),
        "profile": p["key"],
        "summary": {
            "total": meta["total"],
            "detected": meta["detected"],
            "safe": meta["safe"],
            "offline": meta["offline"],
            "critical": meta.get("critical", 0),
        },
        "results": [_json_result(r) for r in results_sorted],
    }

    json_path = os.path.join(output_dir, p["json_name"])
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False, default=str)

    csv_path = os.path.join(output_dir, p["csv_name"])
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if by_kecamatan:
            writer.writerow([
                "no", "status", "nama_desa", "kecamatan", "url",
                "judul_postingan_terakhir", "tanggal_publish", "keterangan",
            ])
        else:
            writer.writerow([
                "no", "status", "nama_instansi", "kategori", "url",
                "judul_postingan_terakhir", "tanggal_publish", "keterangan",
            ])
        for idx, r in enumerate(results_sorted, start=1):
            last = r["last_post"]
            group_val = r.get("kecamatan") if by_kecamatan else r.get("category")
            writer.writerow([
                idx,
                r["status"],
                r["name"],
                group_val or "",
                r["url"],
                (last or {}).get("title", ""),
                _fmt_date((last or {}).get("date")),
                _keterangan(r),
            ])

    return html_path
