# -*- coding: utf-8 -*-
"""
Re-scrape surat keluar (Jan-Agu 2026) untuk 38 peserta lomba dari arsip /keluar
di panel admin OpenSID, agar konsisten dengan angka dashboard OpenSID (mis.
Walikukun 467 -> 474). Memperbarui monthly di output/desa/surat_tercetak.json.

Hasil per desa = {YYYY-MM: n} utk periode penilaian Januari s/d Agustus 2026.
"""
import csv
import json
import os
import re
import sys
import time
import warnings
from bs4 import BeautifulSoup
from collections import Counter

warnings.filterwarnings("ignore")

BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = r"C:\Users\komin\Downloads\OpenSID-Password NEW.xlsx - Lembar1.csv"
PESERTA_PATH = os.path.join(BASE, "output", "lomba", "peserta.json")
SURAT_PATH = os.path.join(BASE, "output", "desa", "surat_tercetak.json")
CKPT_PATH = os.path.join(BASE, "output", "lomba", "keluar_rescan_ckpt.json")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BULAN = {"Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
         "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11, "Desember": 12}


def parse_dt(text):
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})", text)
    if not m:
        return None
    mo = BULAN.get(m.group(2))
    if not mo:
        return None
    return (int(m.group(3)), mo, int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6)))


def in_period(dt):
    """Jan 1 00:00:00 s/d Aug 31 23:59:59 2026."""
    if not dt:
        return False
    y, m = dt[0], dt[1]
    if y != 2026:
        return False
    if m < 1 or m > 8:
        return False
    return True


def login(url, user, passwords):
    base = url.rstrip("/")
    for pw in passwords:
        try:
            s = requests_obj()
            r = s.get(base + "/siteman", timeout=15)
            if r.status_code != 200:
                continue
            csrf = s.cookies.get("sidcsrf", "")
            s.post(base + "/siteman/auth", data={"username": user, "password": pw, "sidcsrf": csrf},
                   timeout=15, allow_redirects=True)
            chk = s.get(base + "/keluar/index/1/0", timeout=15)
            if chk.status_code == 200 and "siteman" not in chk.url:
                return s
        except Exception:
            continue
    return None


def requests_obj():
    import requests
    s = requests.Session()
    s.verify = False
    s.headers.update({"User-Agent": UA})
    return s


def scrape_keluar(session, base):
    """Scrape /keluar pages, stop when past Jan 2026 (archive is newest-first).

    Returns monthly Counter (Jan-Aug 2026 only) and total rows scanned.
    """
    monthly = Counter()
    total_2026 = 0
    page = 1
    max_pages = 500
    empty_streak = 0
    stop_reason = ""
    while page <= max_pages:
        try:
            r = session.get(base + f"/keluar/index/{page}/0", timeout=20)
            if r.status_code != 200:
                stop_reason = f"http_{r.status_code}"
                break
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if not table:
                stop_reason = "no_table"
                break
            headers = [th.get_text(strip=True) for th in table.find_all("th")]
            try:
                tgl_idx = headers.index("Tanggal")
            except ValueError:
                tgl_idx = -1
            tbody = table.find("tbody")
            rows = tbody.find_all("tr") if tbody else []
            got = 0
            all_before_jan2026 = True
            for tr in rows:
                cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
                if tgl_idx >= 0 and tgl_idx < len(cells):
                    dt = parse_dt(cells[tgl_idx])
                    if dt:
                        got = 1
                        y, m = dt[0], dt[1]
                        if y == 2026 and 1 <= m <= 8:
                            monthly[(y, m)] += 1
                            total_2026 += 1
                        if y > 2026 or (y == 2026 and m >= 1):
                            all_before_jan2026 = False
            if got == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    stop_reason = "empty_pages"
                    break
            else:
                empty_streak = 0
                # archive is newest-first; once all rows on this page are
                # before Jan 2026, no need to continue
                if all_before_jan2026:
                    stop_reason = "before_jan2026"
                    break
            page += 1
            time.sleep(0.1)
        except Exception as e:
            stop_reason = f"err_{e}"
            break
    return monthly, total_2026, page, stop_reason


def load_creds():
    rows = list(csv.reader(open(CSV_PATH, encoding="utf-8")))
    m = {}
    for row in rows:
        if row and row[0].strip():
            m[row[0].strip().lower()] = {
                "user": row[1].strip() if len(row) > 1 else "admin",
                "passwords": [p for p in (row[2].strip() if len(row) > 2 else "",
                                          row[3].strip() if len(row) > 3 else "") if p],
            }
    return m


def resolve_creds(desa, url, creds):
    """Find matching CSV credential row for a participant."""
    key_map = {
        "gemarang": "genmarang",          # CSV pakai 'Genmarang'
        "babadan": "babadan pangkur",     # url babadan-pangkur.desa.id
    }
    name = desa.lower()
    if name in key_map:
        name = key_map[name]
    # Karangtengah Prandon -> Karangtengahprandon (CSV)
    if name == "karangtengah prandon":
        name = "karangtengahprandon"
    if name in creds:
        return creds[name]
    # try appending ' ngawi'
    if (name + " ngawi") in creds:
        return creds[name + " ngawi"]
    return None


def main():
    peserta = json.load(open(PESERTA_PATH, encoding="utf-8"))
    creds = load_creds()

    # yang sudah selesai (resume)
    done = {}
    if os.path.exists(CKPT_PATH):
        done = json.load(open(CKPT_PATH, encoding="utf-8"))
        print("Resume:", len(done), "desa selesai")

    results = {}   # desa -> {2026 monthly}
    for p in peserta:
        desa = p["desa"]
        url = p["url"]
        if desa in done:
            results[desa] = done[desa]
            continue
        cred = resolve_creds(desa, url, creds)
        if not cred:
            print(f"{desa:22s} TIDAK ADA KREDENSIAL -> SKIP")
            done[desa] = {"error": "no credentials"}
            continue
        s = login(url, cred["user"], cred["passwords"])
        if not s:
            print(f"{desa:22s} LOGIN GAGAL")
            done[desa] = {"error": "login fail"}
            json.dump(done, open(CKPT_PATH, "w", encoding="utf-8"), ensure_ascii=False)
            continue
        monthly, total_2026, pages, stop = scrape_keluar(s, url.rstrip("/"))
        # konversi key (y,m) -> "YYYY-MM"
        monthly_str = {f"{y}-{m:02d}": c for (y, m), c in monthly.items()}
        s2026 = sum(monthly_str.values())
        done[desa] = {"monthly": monthly_str, "total_2026": total_2026, "pages": pages, "stop": stop}
        results[desa] = done[desa]
        print(f"{desa:22s} Jan-Agu26={s2026:5d} pages={pages:4d} stop={stop}")
        json.dump(done, open(CKPT_PATH, "w", encoding="utf-8"), ensure_ascii=False)

    # --- Update surat_tercetak.json monthly utk 38 peserta ---
    data = json.load(open(SURAT_PATH, encoding="utf-8"))
    name_map = {}   # desa peserta -> nama di surat file
    for r in data.get("results", []):
        name_map[r["name"]] = r["name"]
    # buat peta url snapshot -> nama
    snap = json.load(open(os.path.join(BASE, "output", "desa", "results_desa.json"), encoding="utf-8"))
    url_to_name = {r["url"].rstrip("/").lower(): r["name"] for r in snap.get("results", [])}

    updated = []
    for p in peserta:
        desa = p["desa"]
        res = results.get(desa)
        if not res or res.get("error"):
            continue
        # cari record di surat_tercetak.json
        key = p["url"].rstrip("/").lower()
        snap_name = url_to_name.get(key)
        target = None
        if snap_name:
            for r in data["results"]:
                if r["name"] == snap_name:
                    target = r
                    break
        if not target:
            # coba langsung nama desa
            for r in data["results"]:
                if r["name"].lower().replace(" ", "") == desa.lower().replace(" ", ""):
                    target = r
                    break
        if not target:
            # pemetaan khusus nama desa peserta -> nama di file surat
            special = {
                "GEMARANG": "Genmarang",
                "BABADAN": "Babadan Pangkur",
                "KARANGTENGAH PRANDON": "Karangtengahprandon",
            }
            want = special.get(desa)
            if want:
                for r in data["results"]:
                    if r["name"].lower().replace(" ", "") == want.lower().replace(" ", ""):
                        target = r
                        break
        if target:
            # MERGE, bukan replace: rescan hanya mencakup Jan-Agu 2026,
            # jadi jangan buang bulan/tahun lain (2022-2025, Sep-Des 2026)
            # yang sudah ada sebelumnya.
            old_months = target.get("monthly", {})
            merged = dict(old_months)
            merged.update(res["monthly"])
            target["monthly"] = merged
            target["monthly_parsed"] = sum(merged.values())
            updated.append((desa, snap_name or "?"))
        else:
            print("  warning: tidak ada record utk", desa, "di surat_tercetak.json")

    data["keluar_rescan_2026"] = {
        "note": "Januari s/d Agustus 2026 dari arsip /keluar admin, disinkronkan ke dashboard OpenSID",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(SURAT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nUpdated surat_tercetak.json utk:", len(updated), "desa")

    # ringkasan
    print("\n========== RINGKASAN Jan-Agu 2026 (baru) ==========")
    for p in peserta:
        res = results.get(p["desa"])
        if res and not res.get("error"):
            print(f"  {p['desa']:24s} {sum(res['monthly'].values()):5d}")

    print("\nSelesai.")


if __name__ == "__main__":
    main()
