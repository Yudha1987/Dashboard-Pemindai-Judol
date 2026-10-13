# -*- coding: utf-8 -*-
"""
Re-deteksi komponen "Sinergi Program" utk semua 38 situs dengan aturan baru:
wajib ada label 'sinergi' DAN minimal 1 link eksternal situs pemerintahan
(e-skm, ngawikab.go.id, disdukcapil, dll), bukan sekadar label tanpa link.

Hanya memperbarui field tupoksi_sinergi di check_profil.json.
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
        print(f"  {desa:22s} HOME GAGAL (sinergi tetap lama)")
        continue
    links = chk.extract_links(url, html)

    # kumpulkan halaman profil (sama seperti main) utk konteks link sinergi
    html_blocks = [html]
    text_blocks = [chk.to_text(html)]
    slug_hits = []
    profil_candidates = [l for l in links if any(
        k in chk.strip_slug(l) for k in
        ["sejarah", "visi", "misi", "profil", "struktur", "sotk", "pemerintah",
         "lembaga", "bpd", "lpmd", "perangkat", "aparatur", "karang-taruna",
         "pkk", "rpjm", "sinergi", "peta", "wilayah"])]
    for l in profil_candidates[:chk.MAX_PROFILE_PAGES]:
        ph = chk.fetch(l)
        if ph:
            html_blocks.append(ph)
            text_blocks.append(chk.to_text(ph))
            slug_hits.append(chk.strip_slug(l))

    new_val = chk.check_tupoksi_sinergi(text_blocks, slug_hits, html_blocks, url)
    old_val = rec.get("tupoksi_sinergi")
    rec["tupoksi_sinergi"] = new_val
    flag = "  <-- berubah" if new_val != old_val else ""
    print(f"  {desa:22s} sinergi {old_val} -> {new_val}{flag}")

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("\nSelesai. check_profil.json diperbarui.")
