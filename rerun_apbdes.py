# -*- coding: utf-8 -*-
"""
Re-deteksi APBDes (artikel + galeri gambar) untuk semua 38 situs dengan
logika yang sudah diperbaiki (_apbdes_year + detect_apbdes_gallery), lalu
menggabungkan hanya field apbdes_* ke check_profil.json.
"""
import json
import os
import sys
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import gen_lomba_checker as chk

OUT_PATH = os.path.join(BASE, "output", "lomba", "check_profil.json")
data = json.load(open(OUT_PATH, encoding="utf-8"))

for desa, rec in data.items():
    url = rec.get("url") or rec.get("domain") or rec.get("website")
    if not url:
        url = "https://" + desa.lower().replace(" ", "-") + ".desa.id"

    html = chk.fetch(url)
    if not html:
        print(f"  {desa:22s} HOMEPAGE GAGAL")
        continue
    links = chk.extract_links(url, html)

    # artikel APBDes
    a5, a6, a_detail = chk.detect_apbdes(url, links)

    # APBDes gambar di galeri (first/wilayah paling umum)
    g5 = g6 = False
    g_detail = []
    gal_pages = [html]
    for l in links:
        if "galeri" in urlparse(l).path or "/first/wilayah" in urlparse(l).path:
            gh = chk.fetch(l)
            if gh:
                gal_pages.append(gh)
                break
    for ghtml in gal_pages:
        gg5, gg6, gd = chk.detect_apbdes_gallery(url, links, ghtml)
        g5, g6 = g5 or gg5, g6 or gg6
        g_detail.extend(gd)

    # APBDes multi-lokasi: bottom/footer widget, sidebar, menu, artikel
    w5, w6, w_lokasi = chk.detect_apbdes_locations(url, html, links)

    rec["apbdes_2025"] = a5 or g5 or w5
    rec["apbdes_2026"] = a6 or g6 or w6
    rec["apbdes_detail"] = a_detail + g_detail
    lokasi = {"2025": set(w_lokasi["2025"]), "2026": set(w_lokasi["2026"])}
    for d in a_detail:
        if d.get("tahun") in ("2025", "2026"):
            lokasi[d["tahun"]].add("Ditemukan pada Artikel")
    for d in g_detail:
        if d.get("tahun") in ("2025", "2026"):
            lokasi[d["tahun"]].add("Ditemukan pada Galeri Gambar (upload/galeri/)")
    rec["apbdes_lokasi"] = {"2025": sorted(lokasi["2025"]),
                            "2026": sorted(lokasi["2026"])}
    print(f"  {desa:22s} art(25={a5} 26={a6}) gal(25={g5} 26={g6}) "
          f"widget(25={w5} 26={w6}) => apb25={rec['apbdes_2025']} apb26={rec['apbdes_2026']}")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\nSelesai. check_profil.json diperbarui.")
