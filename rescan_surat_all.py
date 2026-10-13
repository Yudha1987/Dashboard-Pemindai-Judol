# -*- coding: utf-8 -*-
"""
Rescan Surat Tercetak ALL 213 desa — scrape ulang seluruh arsip /keluar
(semua halaman, semua tahun) dan MERGE ke monthly (tidak menimpa/drop).

Berbeda dari rerun_keluar_rescan.py yang hanya menargetkan 38 peserta lomba
dan hanya bulan Jan-Agu 2026: skrip ini men-scrape SEMUA desa dan SEMUA bulan,
sehingga riwayat 2022-2025 (dan seterusnya) terisi lengkap untuk semua desa.

Output: output/desa/surat_tercetak.json (monthly di-merge, surat_tercetak
diperbarui dari widget).
"""
import csv
import json
import os
import re
import sys
import time
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup

from src.scrape_surat import (BULAN_MAP, _find_surat_count, _login,  # noqa: E402
                              _parse_keluar_dates, load_desa_list)

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = r"C:\Users\komin\Downloads\OpenSID-Password NEW.xlsx - Lembar1.csv"
SNAPSHOT_PATH = os.path.join(BASE, "output", "desa", "results_desa.json")
SURAT_PATH = os.path.join(BASE, "output", "desa", "surat_tercetak.json")
CKPT_PATH = os.path.join(BASE, "output", "desa", "surat_all_ckpt.json")
MAX_WORKERS = 2


def scrape_keluar_all(session, base, max_pages=800):
    """Scrape SEMUA halaman /keluar (arsip urut terbaru-dulu), SEMUA tahun.

    Returns (monthly Counter {"YYYY-MM": n}, total_parsed, stop_reason).
    Berhenti bila: 2 halaman kosong beruntun, HTTP != 200, atau max_pages.
    """
    monthly = Counter()
    total_parsed = 0
    page = 1
    empty_streak = 0
    stop_reason = ""
    while page <= max_pages:
        try:
            r = session.get(base + f"/keluar/index/{page}/0", timeout=30)
            if r.status_code != 200:
                stop_reason = "http_%s" % r.status_code
                break
            dates = _parse_keluar_dates(BeautifulSoup(r.text, "html.parser"))
            if not dates:
                empty_streak += 1
                if empty_streak >= 2:
                    stop_reason = "empty_pages"
                    break
                page += 1
                continue
            empty_streak = 0
            for ym in dates:
                monthly[ym] += 1
                total_parsed += 1
            page += 1
            time.sleep(0.1)
        except Exception as e:
            stop_reason = "err_%s" % type(e).__name__
            break
    return monthly, total_parsed, stop_reason


def scrape_one(desa):
    name = desa["name"]
    base = desa["url"].rstrip("/")

    # Login bisa gagal transient saat banyak situs dilihat serentak -> coba ulang
    s = None
    for attempt in range(3):
        s = _login(base, desa["user"], desa["passwords"])
        if s:
            break
        time.sleep(2)
    if not s:
        return {"name": name, "url": base, "ok": False, "error": "login failed"}

    # 1) Total dari widget admin
    total = None
    for admin_path in ("/hom_sid", "/beranda"):
        try:
            r2 = s.get(base + admin_path, timeout=30)
            if r2.status_code != 200 or "siteman" in r2.url:
                continue
            total = _find_surat_count(r2)
            if total is not None:
                break
        except Exception:
            continue
    if total is None:
        total = 0

    # 2) Seluruh bulan dari arsip /keluar
    monthly, parsed, stop = scrape_keluar_all(s, base)

    return {
        "name": name,
        "url": base,
        "ok": True,
        "surat_tercetak": total,
        "monthly": monthly,
        "monthly_parsed": parsed,
        "stop": stop,
    }


def norm(n):
    return re.sub(r"\s+", " ", n.strip()).lower()


def main():
    desa_list = load_desa_list(CSV_PATH, SNAPSHOT_PATH)
    print("Loaded %d desa" % len(desa_list))

    done = {}
    if os.path.exists(CKPT_PATH):
        done = json.load(open(CKPT_PATH, encoding="utf-8"))
        print("Resume: %d selesai" % len(done))

    # Retry: login gagal / error timeout (password baru tersedia di CSV)
    retry = [k for k, v in done.items()
             if (not v.get("ok")) or str(v.get("stop", "")).startswith("err_")]
    for k in retry:
        done.pop(k, None)
    if retry:
        print("Retry karena gagal/timeout: %d" % len(retry))

    remaining = [d for d in desa_list if d["name"] not in done]
    print("Remaining: %d" % len(remaining))
    if not remaining:
        print("Semua sudah selesai.")
        apply_merge(done)
        return

    for batch_start in range(0, len(remaining), 12):
        batch = remaining[batch_start:batch_start + 12]
        futures = {}
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(scrape_one, d): d for d in batch}
            for fut in as_completed(futures):
                r = fut.result()
                done[r["name"]] = r
                if r.get("ok"):
                    print("  [%d/%d] %-24s total=%s parsed=%d stop=%s"
                          % (len(done), len(desa_list), r["name"],
                             r["surat_tercetak"], r["monthly_parsed"], r["stop"]))
                else:
                    print("  [%d/%d] %-24s GAGAL %s"
                          % (len(done), len(desa_list), r["name"], r.get("error")))
        with open(CKPT_PATH, "w", encoding="utf-8") as f:
            json.dump(done, f, ensure_ascii=False)
        time.sleep(0.5)

    apply_merge(done)


def apply_merge(done):
    """Merge hasil rescan ke surat_tercetak.json (semua desa, semua bulan)."""
    data = json.load(open(SURAT_PATH, encoding="utf-8"))
    by_norm = {}
    for r in data.get("results", []):
        by_norm.setdefault(norm(r["name"]), r)

    merged = 0
    for name, res in done.items():
        if not res.get("ok"):
            continue
        target = by_norm.get(norm(name))
        if target is None:
            print("  warning: tak ada record utk", name)
            continue
        old_mo = target.get("monthly", {})
        merged_mo = dict(old_mo)
        merged_mo.update({k: int(v) for k, v in res["monthly"].items()})
        changed = False
        if merged_mo != old_mo:
            target["monthly"] = merged_mo
            target["monthly_parsed"] = sum(merged_mo.values())
            changed = True
        if res["surat_tercetak"] != target.get("surat_tercetak"):
            target["surat_tercetak"] = res["surat_tercetak"]
            changed = True
        if changed:
            merged += 1

    data["total_surat"] = sum(
        r["surat_tercetak"] for r in data.get("results", [])
        if r.get("surat_tercetak") and r["surat_tercetak"] > 0
    )
    with open(SURAT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nmerge selesai: %d desa berubah" % merged)


if __name__ == "__main__":
    main()