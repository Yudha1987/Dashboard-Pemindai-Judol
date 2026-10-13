# -*- coding: utf-8 -*-
"""
Recheck Zero Surat — Re-scan masif seluruh desa yang bermasalah.

Memindai ulang desa dengan surat_tercetak == 0 atau NULL menggunakan
verify_surat_count() dengan dua metode fallback:
  1. Widget/public check (tanpa login)
  2. Login + widget check (dengan credentials dari CSV)

Setelah eksekusi, tampilkan rekap:
  - Total Desa Diperiksa
  - Jumlah Desa Valid (Surat > 0)
  - Jumlah Desa Valid (Surat = 0 Murni)
  - Jumlah Desa Failed/Timeout (Perlu Pengecekan Manual)

Output:
  - audit_surat.log (dari scanner.py)
  - output/desa/surat_tercetak.json (diperbarui)
  - output/desa/audit_report.json (laporan detail)
"""

import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scanner import verify_surat_count
from src.scrape_surat import load_desa_list

CSV_PATH = r"C:\Users\komin\Downloads\OpenSID-Password NEW.xlsx - Lembar1.csv"
SNAPSHOT_PATH = "output/desa/results_desa.json"
SURAT_PATH = "output/desa/surat_tercetak.json"
AUDIT_REPORT_PATH = "output/desa/audit_report.json"
MAX_WORKERS = 5
RETRY = 3
BACKOFF = 5


def load_surat_map():
    """Load surat_tercetak.json, return dict {name: result_dict}."""
    if not os.path.exists(SURAT_PATH):
        return {}
    with open(SURAT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {r["name"]: r for r in data.get("results", [])}


def find_zero_desa():
    """Return list of desa dicts that need re-check (surat=0 or NULL)."""
    surat_map = load_surat_map()
    if not surat_map:
        return []

    zero = []
    for name, entry in surat_map.items():
        count = entry.get("surat_tercetak")
        if count is None or count == 0:
            zero.append(entry)
    return zero


def recheck_one(desa, credentials_map):
    """Re-check satu desa menggunakan verify_surat_count."""
    name = desa.get("name", "")
    url = desa.get("url", "")
    creds = credentials_map.get(name)

    result = verify_surat_count(
        url, credentials=creds, max_retries=RETRY, backoff=BACKOFF
    )

    return {
        "name": name,
        "url": url,
        "old_count": desa.get("surat_tercetak"),
        "new_count": result["count"],
        "scan_status": result["scan_status"],
        "method": result["method"],
        "http_status": result.get("http_status"),
        "error": result.get("error"),
        "retries_used": result.get("retries_used", 0),
    }


def update_surat_json(updates):
    """Update surat_tercetak.json dengan hasil re-check."""
    if not os.path.exists(SURAT_PATH):
        return

    with open(SURAT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    update_map = {u["name"]: u for u in updates}

    changed = 0
    for r in data.get("results", []):
        name = r["name"]
        if name in update_map:
            u = update_map[name]
            if (u["scan_status"] == "VALID"
                    and u["new_count"] is not None
                    and u["new_count"] != r.get("surat_tercetak")):
                r["surat_tercetak"] = u["new_count"]
                r["monthly"] = {}  # monthly perlu scrape terpisah
                r["monthly_parsed"] = 0
                r["note"] = "recheck: %s (%s)" % (
                    u["scan_status"], u["method"]
                )
                changed += 1
            elif u["scan_status"] in ("TIMEOUT", "PENDING_AUDIT"):
                r["note"] = "recheck: %s" % u["scan_status"]

    data["total_surat"] = sum(
        r["surat_tercetak"] for r in data["results"]
        if r.get("surat_tercetak") and r["surat_tercetak"] > 0
    )
    data["success"] = sum(
        1 for r in data["results"] if r.get("surat_tercetak") is not None
    )
    data["failed"] = sum(
        1 for r in data["results"] if r.get("surat_tercetak") is None
    )

    with open(SURAT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return changed


def print_summary(results):
    """Tampilkan rekap ringkas di konsol."""
    total = len(results)
    valid_positive = sum(
        1 for r in results if r["scan_status"] == "VALID" and r["new_count"]
        and r["new_count"] > 0
    )
    valid_zero = sum(
        1 for r in results if r["scan_status"] == "VALID_ZERO"
        or (r["scan_status"] == "VALID" and (r["new_count"] or 0) == 0)
    )
    timeout_count = sum(
        1 for r in results if r["scan_status"] in ("TIMEOUT", "PENDING_AUDIT")
    )

    print("\n" + "=" * 60)
    print("  REKAPITULASI AUDIT SURAT TERCETAK")
    print("=" * 60)
    print("  Total Desa Diperiksa          : %d" % total)
    print("  Valid (Surat > 0)             : %d" % valid_positive)
    print("  Valid (Surat = 0 Murni)       : %d" % valid_zero)
    print("  Failed/Timeout (Perlu Manual) : %d" % timeout_count)
    print("=" * 60)

    if valid_positive > 0:
        print("\n  Desa yang BERUBAH dari 0 -> angka:")
        for r in results:
            if r["scan_status"] == "VALID" and r["new_count"] and r["new_count"] > 0:
                print("    + %-30s %d surat (via %s)" % (
                    r["name"], r["new_count"], r["method"]
                ))

    if timeout_count > 0:
        print("\n  Desa yang PERLU pengecekan manual:")
        for r in results:
            if r["scan_status"] in ("TIMEOUT", "PENDING_AUDIT"):
                print("    ! %-30s %s" % (
                    r["name"], r.get("error", "unknown")
                ))

    print("")


def main():
    print("Loading desa list...")
    desa_list = load_desa_list(CSV_PATH, SNAPSHOT_PATH)
    print("Loaded %d desa" % len(desa_list))

    surat_map = load_surat_map()
    credentials_map = {}
    for d in desa_list:
        if d["name"] in surat_map:
            credentials_map[d["name"]] = d

    zero_desa = find_zero_desa()
    print("Found %d desa with surat=0 or NULL" % len(zero_desa))

    if not zero_desa:
        print("Tidak ada desa yang perlu di-recheck.")
        return

    print("\nMulai re-check (%d worker, %d retry, %ds backoff)..." % (
        MAX_WORKERS, RETRY, BACKOFF
    ))
    start = time.time()

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(recheck_one, d, credentials_map): d
            for d in zero_desa
        }
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            results.append(r)
            status_char = {
                "VALID": "+",
                "VALID_ZERO": "0",
                "TIMEOUT": "!",
                "PENDING_AUDIT": "?",
            }.get(r["scan_status"], "?")
            count_str = str(r["new_count"]) if r["new_count"] is not None else "N/A"
            print("  [%d/%d] %s %-30s -> %s (count=%s, method=%s)" % (
                i, len(zero_desa), status_char, r["name"],
                r["scan_status"], count_str, r["method"]
            ))

    elapsed = time.time() - start
    print("\nSelesai dalam %.1f detik" % elapsed)

    print_summary(results)

    # Simpan audit report
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_checked": len(results),
        "results": results,
    }
    with open(AUDIT_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("Audit report tersimpan: %s" % AUDIT_REPORT_PATH)

    # Update surat_tercetak.json
    changed = update_surat_json(results)
    print("surat_tercetak.json diperbarui: %d desa berubah" % changed)


if __name__ == "__main__":
    main()
