# -*- coding: utf-8 -*-
"""
Scrape Surat Tercetak dari admin panel semua desa.

Versi 2 - dengan data bulanan:
- Total akumulasi dari widget dashboard (/hom_sid atau /beranda)
- Log riwayat surat dari /keluar/clear/masuk (arsip layanan)
- Agregasi per bulan/tahun berdasarkan tanggal cetak

Output:
- output/desa/surat_tercetak.json dengan field monthly{}
"""
import requests
import warnings
import re
import json
import time
import csv
import os
from bs4 import BeautifulSoup
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings("ignore")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CKPT = "output/desa/surat_monthly_ckpt.json"

BULAN_MAP = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
    "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
    "September": 9, "Oktober": 10, "November": 11, "Desember": 12,
}


def load_desa_list(csv_path, snapshot_path):
    """Load desa list, match CSV passwords with snapshot URLs."""
    snap = json.load(open(snapshot_path, encoding="utf-8"))
    url_by_name = {}
    for r in snap["results"]:
        if r["url"].endswith(".desa.id"):
            url_by_name[r["name"]] = r["url"]

    name_variants = {}
    for r in snap["results"]:
        base_name = r["name"].replace(" Ngawi", "").replace(" - ", "-")
        name_variants[base_name] = r["name"]

    desa_list = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip():
                continue
            csv_name = row[0].strip()
            user = row[1].strip() if len(row) > 1 else "admin"
            pw1 = row[2].strip() if len(row) > 2 else ""
            pw2 = row[3].strip() if len(row) > 3 else ""
            passwords = [p for p in [pw1, pw2] if p]
            if not passwords:
                continue

            snap_name = url_by_name.get(csv_name)
            if snap_name:
                url = url_by_name[csv_name]
            else:
                variant = name_variants.get(csv_name)
                if variant and variant in url_by_name:
                    url = url_by_name[variant]
                else:
                    slug = csv_name.lower().replace(" ", "-")
                    url = f"https://{slug}.desa.id"

            desa_list.append({"name": csv_name, "url": url, "user": user, "passwords": passwords})

    return desa_list


def _find_surat_count(soup):
    """Find surat tercetak count from admin dashboard HTML."""
    for div in soup.find_all(["div", "span"]):
        text = div.get_text(" ", strip=True)
        m = re.match(r"^(\d+)\s*Surat\s+Tercetak", text)
        if m:
            return int(m.group(1))

    for h3 in soup.find_all("h3"):
        t = h3.get_text(strip=True)
        if re.match(r"^\d+$", t):
            nxt = h3.find_next_sibling()
            if nxt and "surat" in nxt.get_text(strip=True).lower():
                return int(t)
            parent = h3.parent
            if parent:
                for sib in parent.find_all(["p", "span", "div"]):
                    if "surat" in sib.get_text(strip=True).lower():
                        return int(t)

    for div in soup.find_all("div"):
        text = div.get_text(" ", strip=True)
        m = re.search(r"(\d+)\s*Surat\s+Tercetak", text)
        if m:
            return int(m.group(1))

    return None


def _parse_keluar_dates(soup):
    """Parse Tanggal column from a single /keluar page table.

    Returns list of "YYYY-MM" date strings from all rows on the page.
    """
    table = soup.find("table")
    if not table:
        return []

    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    tgl_idx = -1
    for i, h in enumerate(headers):
        if "tanggal" in h.lower():
            tgl_idx = i
            break
    if tgl_idx < 0:
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    dates = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if tgl_idx < len(cells):
            date_text = cells[tgl_idx].get_text(strip=True)
            m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_text)
            if m:
                month_num = BULAN_MAP.get(m.group(2), 0)
                if month_num:
                    dates.append(f"{m.group(3)}-{month_num:02d}")
    return dates


def _scrape_all_keluar_dates(session, base):
    """Paginate /keluar/index/{page}/0 to collect ALL letter dates.

    Returns (monthly_dict, total_parsed, is_complete)
    - monthly_dict: {"2024-03": 5, "2024-04": 12, ...}
    - total_parsed: total rows parsed across all pages
    - is_complete: True if pagination completed (all records scraped)
    """
    monthly = Counter()
    total_parsed = 0
    page = 1
    max_pages = 500
    consecutive_empty = 0

    while page <= max_pages:
        try:
            r = session.get(f"{base}/keluar/index/{page}/0", timeout=15)
            if r.status_code != 200:
                break
            dates = _parse_dates_from_html(r.text)
            if not dates:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                page += 1
                continue
            consecutive_empty = 0
            for d in dates:
                monthly[d] += 1
                total_parsed += 1
            page += 1
            time.sleep(0.15)
        except Exception:
            break

    return dict(monthly), total_parsed, page > 2


def _parse_dates_from_html(html_text):
    """Extract date strings from a single HTML page's table."""
    soup = BeautifulSoup(html_text, "html.parser")
    return _parse_keluar_dates(soup)


def _login(base, user, passwords):
    """Try to login, return session or None."""
    for pw in passwords:
        for attempt in range(3):
            try:
                s = requests.Session()
                s.verify = False
                s.headers.update({
                    "User-Agent": UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
                })
                r = s.get(f"{base}/siteman", timeout=15)
                if r.status_code != 200:
                    raise RuntimeError("siteman http %s" % r.status_code)
                csrf = s.cookies.get("sidcsrf", "")
                s.headers.update({
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": f"{base}/siteman",
                })
                r = s.post(f"{base}/siteman/auth", data={
                    "username": user, "password": pw, "sidcsrf": csrf,
                }, timeout=25, allow_redirects=True)
                if r.status_code != 200:
                    raise RuntimeError("auth http %s" % r.status_code)
                # Login gagal bila final url kembali ke halaman siteman
                final = r.url.rstrip("/")
                if final.endswith("siteman") or "/siteman/auth" in final:
                    continue
                return s
            except Exception:
                continue
        # jeda sebentar antar password agar tidak kena rate-limit
        time.sleep(2)
    return None


def scrape_one(desa):
    """Scrape total + monthly data for one desa."""
    name = desa["name"]
    base = desa["url"]

    s = _login(base, desa["user"], desa["passwords"])
    if not s:
        return {"name": name, "url": base, "surat_tercetak": None,
                "monthly": {}, "monthly_parsed": 0, "note": "login failed"}

    # Step 1: Get total from widget
    total = None
    for admin_path in ["/hom_sid", "/beranda"]:
        try:
            r2 = s.get(f"{base}{admin_path}", timeout=10)
            if r2.status_code != 200 or "siteman" in r2.url:
                continue
            soup = BeautifulSoup(r2.text, "html.parser")
            total = _find_surat_count(soup)
            if total is not None:
                break
        except Exception:
            continue

    if total is None:
        total = 0

    # Step 2: Get monthly data via paginated /keluar/index/{page}/0
    monthly = {}
    monthly_parsed = 0
    is_complete = False
    try:
        monthly, monthly_parsed, is_complete = _scrape_all_keluar_dates(s, base)
    except Exception:
        pass

    note = ""
    if total == 0 and monthly_parsed == 0:
        note = "no widget"
    elif not is_complete and monthly_parsed > 0:
        note = f"partial ({monthly_parsed} rows)"

    return {
        "name": name,
        "url": base,
        "surat_tercetak": total,
        "monthly": monthly,
        "monthly_parsed": monthly_parsed,
        "note": note,
    }


def main():
    csv_path = r"C:\Users\komin\Downloads\OpenSID-Password NEW.xlsx - Lembar1.csv"
    snapshot_path = "output/desa/results_desa.json"
    desa_list = load_desa_list(csv_path, snapshot_path)
    print(f"Loaded {len(desa_list)} desa")

    done = {}
    if os.path.exists(CKPT):
        ckpt = json.load(open(CKPT, encoding="utf-8"))
        done = {r["name"]: r for r in ckpt.get("results", [])}
        print(f"Resuming: {len(done)} done")

    remaining = [d for d in desa_list if d["name"] not in done]
    print(f"Remaining: {len(remaining)}")

    results = list(done.values())

    for batch_start in range(0, len(remaining), 10):
        batch = remaining[batch_start:batch_start + 10]
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {ex.submit(scrape_one, d): d for d in batch}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
                status = r["surat_tercetak"] if r["surat_tercetak"] is not None else r.get("note", "?")
                mo = len(r.get("monthly", {}))
                print(f"  [{len(results)}/{len(desa_list)}] {r['name']}: {status} ({mo} months)")
        with open(CKPT, "w", encoding="utf-8") as f:
            json.dump({"results": results}, f, ensure_ascii=False)
        time.sleep(1)

    # Build summary
    success = sum(1 for r in results if r.get("surat_tercetak") is not None)
    failed = sum(1 for r in results if r.get("surat_tercetak") is None)
    total_surat = sum(r["surat_tercetak"] for r in results if r.get("surat_tercetak"))

    # Aggregate all monthly data
    all_months = Counter()
    for r in results:
        for ym, cnt in r.get("monthly", {}).items():
            all_months[ym] += cnt

    output = "output/desa/surat_tercetak.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "total_desa": len(desa_list),
            "success": success,
            "failed": failed,
            "total_surat": total_surat,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nDone! {success}/{len(desa_list)} success, {total_surat} total surat")
    print(f"Monthly aggregation: {dict(sorted(all_months.items()))}")

    # Also save separate monthly summary
    monthly_path = "output/desa/surat_monthly.json"
    with open(monthly_path, "w", encoding="utf-8") as f:
        json.dump({
            "months": dict(sorted(all_months.items())),
            "per_desa": [
                {"name": r["name"], "monthly": r.get("monthly", {})}
                for r in results if r.get("monthly")
            ],
        }, f, indent=2, ensure_ascii=False)
    print(f"Monthly summary saved to {monthly_path}")


if __name__ == "__main__":
    main()
