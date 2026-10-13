# -*- coding: utf-8 -*-
"""Re-detect default OpenSID content (Senggigi/Lombok) for the affected villages,
then apply authenticity override to check_profil.json."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_lomba_checker as g

OUT_PATH = g.OUT_PATH
out = json.load(open(OUT_PATH, encoding='utf-8'))

# Where to re-scan: all villages that currently have history/SOTK true, so we
# re-detect default signatures uniformly and don't miss any.
targets = list(out.keys())

# rebuild profil candidates + text_blocks for each village (subset re-fetch)
for desa in targets:
    rec = out[desa]
    url = rec.get('url')
    if not url or not rec.get('done'):
        continue
    html = g.fetch(url)
    if not html:
        print(f"{desa:24s} HOMEPAGE FAIL"); continue
    links = g.extract_links(url, html)
    text_blocks, slug_hits = [g.to_text(html)], []
    cand = []
    MAX = 5
    for l in links:
        slug = g.strip_slug(l)
        if any(k in slug for k in ['sejarah','visi','misi','profil-desa','struktur','sotk',
                                   'perangkat','aparatur','lembaga','bpd','lpmd','data-desa',
                                   'data-wilayah','peta','wilayah']):
            cand.append(l)
        elif '/peta' in l or 'data-wilayah' in l.lower():
            cand.append(l)
    seen = set(); cand_dedup = []
    for l in cand:
        if l not in seen:
            seen.add(l); cand_dedup.append(l)
    for l in cand_dedup[:MAX]:
        ph = g.fetch(l)
        if ph:
            text_blocks.append(g.to_text(ph))
            slug_hits.append(g.strip_slug(l))

    # Deterministic: probe OpenSID default-dated sample articles if present at all.
    # These are the well-known default URLs: visi-dan-misi (24/8/2016), sejarah
    # (26/8/2016), struktur-organisasi. Catch them even if not in first MAX pages.
    from urllib.parse import urlsplit
    base = urlsplit(url.rstrip('/')).scheme + '://' + urlsplit(url).netloc
    default_urls = [
        base + '/artikel/2016/8/24/visi-dan-misi',
        base + '/artikel/2016/8/26/sejarah-desa',
        base + '/artikel/2016/8/26/struktur-organisasi',
        base + '/artikel/2016/8/24/susunan-organisasi-pemerintahan-desa',
    ]
    for du in default_urls:
        ph = g.fetch(du)
        if ph:
            text_blocks.append(g.to_text(ph))
            slug_hits.append('default:' + du.split('/artikel/')[-1])

    # recompute the relevant components from scratch + default override
    rec['sejarah_dan_visimisi'] = g.check_sejarah_visimisi(text_blocks, slug_hits)
    rec['sotk_struktur'] = g.check_sotk_struktur(text_blocks, slug_hits)
    rec['sotk_lembaga'] = g.check_sotk_lembaga(text_blocks, slug_hits)
    rec['tupoksi_peta'] = g.check_tupoksi_peta(text_blocks, slug_hits, links)

    default_hits = g.detect_default_content(text_blocks, slug_hits)
    for comp in default_hits:
        rec[comp] = False
    rec['konten_default'] = sorted(default_hits)
    # update catatan
    rec['catatan'] = [c for c in rec.get('catatan', []) if 'KONTEN DEFAULT OpenSID' not in c]
    if default_hits:
        rec['catatan'].append(
            "KONTEN DEFAULT OpenSID: " + ", ".join(sorted(default_hits)) +
            " masih terisi contoh bawaan 'Desa Senggigi (Lombok)', bukan konten desa "
            "(komponen tsb dianggap 0).")
    print(f"{desa:24s} sejarah={rec['sejarah_dan_visimisi']} sotk={rec['sotk_struktur']} "
          f"lembaga={rec['sotk_lembaga']} peta={rec['tupoksi_peta']} default={default_hits}")

json.dump(out, open(OUT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print("\nSaved:", OUT_PATH)
