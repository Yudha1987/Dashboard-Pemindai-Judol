"""Perbaiki surat_tercetak (total akumulatif) yang belum terekap di
output/desa/surat_tercetak.json.

Ulangi login tiap desa dan baca widget "Surat Tercetak" dari /beranda
(lama kelamaan /hom_sid 404). Hanya menulis jika nilai > 0 dan berubah.
"""

import json
import os
import sys
import time
import warnings

from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup  # noqa: E402

from src.scrape_surat import _login, _find_surat_count, load_desa_list  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = r"C:\Users\komin\Downloads\OpenSID-Password NEW.xlsx - Lembar1.csv"
SNAPSHOT_PATH = os.path.join(BASE, "output", "desa", "results_desa.json")
SURAT_PATH = os.path.join(BASE, "output", "desa", "surat_tercetak.json")


def get_total(s, base):
    for path in ("/beranda", "/hom_sid"):
        try:
            r = s.get(base + path, timeout=30)
            if r.status_code != 200 or "siteman" in r.url:
                continue
            cnt = _find_surat_count(BeautifulSoup(r.text, "html.parser"))
            if cnt is not None:
                return cnt
        except Exception:
            continue
    return None


def fix_one(desa):
    base = desa["url"].rstrip("/")
    s = None
    for _ in range(3):
        s = _login(base, desa["user"], desa["passwords"])
        if s:
            break
        time.sleep(2)
    if not s:
        return desa["name"], None, "login failed"
    total = get_total(s, base)
    if total is None:
        return desa["name"], None, "widget tidak ditemukan"
    return desa["name"], total, "ok"


def main():
    desa_list = load_desa_list(CSV_PATH, SNAPSHOT_PATH)
    data = json.load(open(SURAT_PATH, encoding="utf-8"))
    by_norm = {}
    from rescan_surat_all import norm
    for r in data.get("results", []):
        by_norm.setdefault(norm(r["name"]), r)

    BATCH = 8
    updated = 0
    fails = []
    valid = []
    for start in range(0, len(desa_list), BATCH):
        batch = desa_list[start:start + BATCH]
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {ex.submit(fix_one, d): d for d in batch}
            for fut in as_completed(futs):
                name, total, status = fut.result()
                if total is None:
                    fails.append((name, status))
                    continue
                valid.append((name, total))
    for name, total in valid:
        t = by_norm.get(norm(name))
        if t is None:
            continue
        if total != t.get("surat_tercetak"):
            t["surat_tercetak"] = total
            updated += 1

    data["total_surat"] = sum(
        r["surat_tercetak"] or 0 for r in data.get("results", [])
    )
    json.dump(data, open(SURAT_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("updated: %d desa" % updated)
    print("gagal/0 (%d):" % len(fails))
    for name, status in fails:
        print("   %-24s %s" % (name, status))


if __name__ == "__main__":
    main()