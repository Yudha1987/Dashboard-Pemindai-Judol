# -*- coding: utf-8 -*-
"""
Checker Lomba Website Desa OpenSID 2026.

Menjelajah 38 situs peserta dan mendeteksi kehadiran konten per komponen:
  - sejarah_dan_visimisi  : ada konten Sejarah Desa + Visi & Misi      (5)
  - sotk_struktur         : ada konten SOTK / Struktur Organisasi     (5)
  - sotk_lembaga          : ada konten Lembaga Desa (BPD/LPMD/dll)    (5)
  - tupoksi_peta          : ada Peta / peta wilayah desa              (5)
  - tupoksi_sinergi       : ada konten Sinergi Program                (5)
  - kualitas_berita       : kualitas berita 5W+1H pada artikel 2026   (10)
  - kuantitas_2026        : jumlah artikel Jan s/d Agu 2026           (10, auto)

Hasil ditulis ke output/lomba/check_profil.json (resumable, per-situs).
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
import requests.adapters

requests.packages.urllib3.disable_warnings()

BASE = os.path.dirname(os.path.abspath(__file__))
PESERTA_PATH = os.path.join(BASE, "output", "lomba", "peserta.json")
OUT_PATH = os.path.join(BASE, "output", "lomba", "check_profil.json")

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 25
RETRIES = 2

# Batas jumlah request agar durasi terkendali
MAX_PROFILE_PAGES = 5      # halaman diprioritaskan utk profil/lembaga/peta/sinergi
MAX_ARTIKEL_SAMPLE = 6     # artikel 2026 terbaru utk penilaian kualitas 5W+1H


def fetch(url):
    html = None
    for attempt in range(RETRIES):
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=0)
        s.mount("https://", a)
        s.mount("http://", a)
        try:
            r = s.get(url, timeout=TIMEOUT, headers=HEADERS, verify=False,
                      allow_redirects=True)
            if r.status_code == 200:
                html = r.text
                return html
            return None
        except Exception:
            html = None
        finally:
            s.close()
        if attempt < RETRIES - 1:
            time.sleep(0.5)
    return None


def extract_links(base_url, html):
    """Kumpulkan semua tautan internal (absolut maupun relatif)."""
    links = set()
    for m in re.finditer(r'href=["\']([^"\'#][^"\']*)["\']', html):
        href = m.group(1).strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        try:
            full = urljoin(base_url, href)
        except Exception:
            continue
        if full.startswith(base_url.rstrip("/")) or full.startswith(
                urlparse(base_url).scheme + "://" + urlparse(base_url).netloc):
            links.add(full)
    return links


def to_text(html):
    if not html:
        return ""
    txt = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<style[^>]*>.*?</style>", " ", txt, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;?", " ", txt)
    txt = re.sub(r"&amp;", "&", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt.strip()


def strip_slug(url):
    return re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", urlparse(url).path.lower())


def article_date_from_path(path):
    m = re.search(r"/artikel/(\d{4})/(\d{1,2})/(\d{1,2})", path)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


# ---- Klasifikasi komponen ----
def check_sejarah_visimisi(text_blocks, slug_hits):
    """Konten Sejarah Desa + Visi & Misi."""
    joined = " ".join(text_blocks).lower()
    if not joined:
        return False
    has_sejarah = ("sejarah desa" in joined or "sejarah" in joined) and (
        "berdiri" in joined or "terbentuk" in joined or "asal usul" in joined
        or "sejarah desa" in joined)
    has_sejarah_simple = "sejarah desa" in joined
    has_visi = "visi" in joined
    has_misi = "misi" in joined
    # Ada halaman khusus sejarah/visi-misi
    has_page = any(k in s for s in slug_hits for k in ("sejarah", "visi-misi", "visi-dan-misi"))
    return (has_sejarah_simple or has_page) and has_visi and has_misi


def check_sotk_struktur(text_blocks, slug_hits):
    joined = " ".join(text_blocks).lower()
    if not joined:
        return False
    return bool(re.search(r"struktur organisasi|strukturorg|struktur org|sotk|struktur pemerintahan", joined)) \
        or ("perangkat desa" in joined and "kepala desa" in joined)


def check_sotk_lembaga(text_blocks, slug_hits):
    joined = " ".join(text_blocks).lower()
    if not joined:
        return False
    keys = ["bpd", "badan permusyawaratan desa", "lpmd", "lembaga kemasyarakatan",
            "karang taruna", "lembaga desa", "pkk", "kelompok tani", "pokmasdas",
            "badan usaha milik desa", "bumdes", "tim penggerak pkk"]
    return any(k in joined for k in keys)


def check_tupoksi_peta(text_blocks, slug_hits, links):
    joined = " ".join(text_blocks).lower()
    has_peta_page = any("/peta" in l or "data-wilayah" in l or "peta-wilayah" in l for l in links)
    if has_peta_page:
        return True
    if "peta desa" in joined or "peta wilayah" in joined or "peta lokasi" in joined:
        return True
    # embed peta (iframe/script google maps)
    return False


# ---- Deteksi konten DEFAULT OpenSID (Desa Senggigi / Lombok) ----
# Beberapa situs baru instalasi masih memakai contoh bawaan OpenSID:
#   - Sejarah: paragraf "pulau lombok pernah menjadi wilayah kekuasaan kerajaan
#     karang asem bali / anak agung gde jelantik"
#   - Visi-Misi: "senggigi berseri (bersih, relegius, sejahtera, rapi, indah)"
#   - SOTK: pejabat bawaan "kepala desa: muhammad ilham" & "sekretaris desa: mustahiq"
# Detector ini hanya menandai teks bawaan tsb, TANPA menolak konten otentik desa.
DEFAULT_SIGNATURES = {
    "sejarah_dan_visimisi": [
        # Sejarah default: paragraf pulau lombok
        r"pulau lombok pernah menjadi wilayah kekuasaan",
        r"kerajaan karang \s?asem bali",
        r"anak agung gde? jelantik",
        r"rakyat lombok yang dianggap tertindas",
        # Visi-Misi default: "senggigi berseri" / "masyarakat desa senggigi"
        r"senggigi berseri",
        r"desa senggigi yang bersih, relegius",
        r"terwujudnya masyarakat desa senggigi",
    ],
    "sotk_struktur": [
        r"kepala desa:\s*muhammad ilham",
        r"sekretaris desa:\s*mustahiq",
        r"kepala desa muhammad ilham",
    ],
}

# Apabila teks default Senggigi ditemukan pada halaman apa pun (home/profil),
# komponen terkait dianggap BELUM diisi konten asli -> skor 0.
def detect_default_content(text_blocks, slug_hits):
    joined = " ".join(text_blocks).lower()
    affected = set()
    for comp, pats in DEFAULT_SIGNATURES.items():
        if any(re.search(p, joined) for p in pats):
            affected.add(comp)
    return affected


SINERGI_GOV_KEYWORDS = [
    "egov", "e-gov", "e-govt", "e-skm", "eskm", "skm",
    "ngawikab", "disdukcapil", "dukcapil", "pendidikankab",
    "kemendagri", "jpp.kemendagri", "kemendesa", "kemendes",
    "bpjs", "kemenkominfo", "kemenkes", "kemenag",
    "pemkab", "pemprov", "dinas", "dinkes", "dindik",
    "kab.go.id", "prov.go.id", "go.id", "bps.go.id", "ppid",
    "sipp", "lapor.go.id", "jdih", "sipd", "desa.go.id",
    "pmd", "binamarga", "puskesmas", "kepolisian", "polres",
]


def _window_has_gov_link(window_html, base_netloc):
    """Cek apakah segmen HTML memuat minimal 1 link eksternal pemerintahan."""
    for m in re.finditer(r'<a[^>]*href=["\'](https?://[^"\'>#]+)["\'][^>]*>(.*?)</a>',
                         window_html, re.S | re.I):
        href = m.group(1).strip()
        try:
            netloc = urlparse(href).netloc.lower()
        except Exception:
            continue
        if not netloc:
            continue
        # lewati link ke domain desa sendiri
        if netloc == base_netloc or netloc.endswith("." + base_netloc):
            continue
        anchor = re.sub(r"<[^>]+>", " ", m.group(2))
        blob = (href + " " + anchor).lower()
        if any(k in blob for k in SINERGI_GOV_KEYWORDS):
            return True
    return False


def check_tupoksi_sinergi(text_blocks, slug_hits, html_blocks, base_url):
    """Sinergi Program robust: wajib ada label 'sinergi' DAN minimal 1 link
    eksternal situs pemerintahan desa (e-skm, ngawikab.go.id, disdukcapil, dll)
    dalam bagian sinergi — bukan sekadar label/kata tanpa link."""
    joined = " ".join(text_blocks).lower()
    if not joined:
        return False
    has_label = ("sinergi program" in joined) or (
        "sinergi" in joined and ("program" in joined or "kegiatan" in joined))
    if not has_label:
        return False
    base_netloc = urlparse(base_url).netloc.lower()
    for h in html_blocks:
        low = h.lower()
        for m in re.finditer(r"sinergi", low):
            s = max(0, m.start() - 250)
            e = min(len(h), m.end() + 800)
            if _window_has_gov_link(h[s:e], base_netloc):
                return True
    return False


# ---- APBDes teliti (Realisasi APBDes 2025 & 2026) ----
def _slug_tail(path):
    """Ambil bagian kata-kata slug setelah prefix `artikel/YYYY/M/D/`."""
    m = re.search(r"/artikel/\d{4}/\d{1,2}/\d{1,2}/(.+)$", path)
    if m:
        return m.group(1)
    m = re.search(r"/artikel/(.+)$", path)
    if m:
        return m.group(1)
    return path


def _apbdes_year(path, text):
    """Tentukan tahun APBDes (2025/2026) dari slug-judul halaman, bukan tanggal publikasi."""
    tail = _slug_tail(path).lower()
    if "kategori" in tail:
        return None
    # Tahun yang disebutkan SETELAH token 'apbdes' pada slug (paling andal).
    m = re.search(r"apbdesa?\b[^0-9]{0,45}(20(?:2[56]))", tail)
    if m:
        return m.group(1)
    # Fallback: cari tahun di sekitar 'realisasi apbdes ... tahun YYYY' pada awal teks.
    m = re.search(r"realisasi[^.!?]{0,70}?(?:tahun|anggaran)?\s*(20(?:2[56]))", text[:1500].lower())
    if m:
        return m.group(1)
    return None


def _is_realisasi_apbdes(page_title, slug, text):
    """Apakah halaman ini publikasi Realisasi APBDes (bukan sekadar berita)."""
    blob = (page_title + " " + slug).lower()
    is_apbdes = "apbdes" in blob or "apbd " in blob or "anggaran pendapatan" in blob
    if not is_apbdes:
        return False
    low = text.lower()
    # indikator punya isi angka realisasi
    has_figures = bool(re.search(r"\brp\.?\s|rp\s+\d|\b\d{1,3}(?:\.\d{3})+\b", low))
    has_realisasi_word = "realisasi" in blob or "realisasi" in low
    has_finance_words = any(k in low for k in ["pendapatan", "belanja", "anggaran",
                                                "penerimaan", "pengeluaran", "silpa",
                                                "pad", "pajak", "hasil", "program"])
    content_len = len(text)
    return (has_figures or has_finance_words) and (has_realisasi_word or content_len > 800)


def detect_apbdes(base_url, links):
    """Cari halaman Realisasi APBDes 2025 & 2026 secara teliti.

    Mengembalikan (apbdes_2025, apbdes_2026, detail).
    """
    apbdes_candidates = []
    for l in links:
        path = urlparse(l).path
        slug = strip_slug(l)
        if "kategori" in path:
            continue
        if "apbdes" in slug or "apbd" in slug or "realisasi" in slug:
            apbdes_candidates.append(l)
    # dedupe
    seen = set()
    apbdes_candidates = [l for l in apbdes_candidates
                         if not (l in seen or seen.add(l))]

    def _priority(l):
        # Dahulukan halaman yang jelas memuat tahun APBDes 2025/2026 pada slug
        # (mis. realisasi-apbdes-2026, apbdes-tahun-anggaran-2025) dan hindari
        # berita rapat musyawarah yang bukan dokumen realisasi.
        slug = strip_slug(l).lower()
        has_yr = bool(re.search(r"(?:apbdes|realisasi|anggaran|tahun)[a-z0-9-]{0,20}?20(?:2[56])", slug))
        talks_meeting = bool(re.search(r"musyawarah|musrenbang|musdes|rapat|sosialisasi", slug))
        score = 0
        if "realisasi" in slug:
            score += 30
        if has_yr:
            score += 20
        if talks_meeting:
            score -= 40
        return (-score, slug)

    apbdes_candidates.sort(key=_priority)

    found = {"2025": None, "2026": None}
    detail = []
    for l in apbdes_candidates[:8]:
        ph = fetch(l)
        if not ph:
            continue
        title = strip_slug(l)
        text = to_text(ph)
        path = urlparse(l).path
        if not _is_realisasi_apbdes(title, path, text):
            continue
        year = _apbdes_year(path, text)
        if year in ("2025", "2026") and not found[year]:
            found[year] = l
        detail.append({"url": l, "tahun": year,
                       "panjang": len(text)})

    return (found["2025"] is not None, found["2026"] is not None, detail)


def detect_apbdes_gallery(base_url, wired, html):
    """Deteksi APBDes yang dipublikasikan sebagai GAMBAR di galeri.

    Beberapa desa memajang dokumen APBDes sebagai gambar (folder
    `upload/galeri/`) dengan judul/keterangan (alt/title/nama-file) yang
    menyebut 'APBDes' + tahun. Fungsi ini men-scan halaman (homepage atau
    `first/wilayah`) dan mendeteksi tahun 2025/2026 dari keterangan gambar.

    Mengembalikan (apbdes_2025, apbdes_2026, detail_gambar).
    """
    found = {"2025": None, "2026": None}
    detail = []
    if not html:
        return (False, False, [])
    # scan semua img di folder galeri -> alt/title/nama file
    for m in re.finditer(r'<img[^>]*src=["\']([^"\']*upload/galeri/[^"\']*)["\'][^>]*>', html, re.I):
        tag = m.group(0)
        src = m.group(1)
        alt = re.search(r'alt=["\']([^"\']*)["\']', tag, re.I)
        title = re.search(r'title=["\']([^"\']*)["\']', tag, re.I)
        label = (alt.group(1) if alt else "") + " " + (title.group(1) if title else "") + " " + src.split("/")[-1]
        blob = label.lower()
        if "apbdes" not in blob and "apbd " not in blob:
            continue
        # tahun dari label/keterangan
        year = None
        yr = re.search(r"(?:apbdes|realisasi|anggaran|tahun)[^\d]{0,15}?(20(?:2[56]))", blob) \
            or re.search(r"(20(?:2[56]))", blob)
        if yr:
            year = yr.group(1)
        if year in ("2025", "2026") and not found[year]:
            found[year] = src
        detail.append({"url": src, "tahun": year, "keterangan": label.strip()[:120]})
    return (found["2025"] is not None, found["2026"] is not None, detail)


# ---- APBDes multi-lokasi (variasi tata letak OpenSID) ----
def _apbdes_year_from_text(low):
    """Tentukan tahun APBDes 2025/2026 dari teks sesuai daftar kata kunci
    (APBDes 2025, Realisasi 2025, Pelaksanaan 2025, Pendapatan 2025,
    Pembelanjaan 2025, Anggaran ____, Transparansi 2026)."""
    for yr in ("2026", "2025"):
        for pat in ("apbdes", "realisasi", "pelaksanaan", "pendapatan",
                    "pembelanjaan", "anggaran", "transparansi"):
            if re.search(r"%s[^\d]{0,8}%s" % (pat, yr), low):
                return yr
    m = re.search(r"apbdes[^\d]{0,15}(20(?:2[56]))", low)
    if m:
        return m.group(1)
    m = re.search(r"(?:realisasi|anggaran|tahun)[^\d]{0,15}(20(?:2[56]))", low)
    if m:
        return m.group(1)
    return None


def _dom_region(tag):
    """Klasifikasi lokasi DOM sebuah elemen: menu / sidebar / footer / None."""
    cur = tag
    while cur is not None:
        cls = " ".join(cur.get("class") or [])
        ids = cur.get("id") or ""
        blob = (cls + " " + ids).lower()
        if "sidebar" in blob or "widget-area" in blob or cur.name == "aside":
            return "sidebar"
        if ("footer" in blob or "footer-bottom" in blob
                or "footer_top" in blob or "widget-footer" in blob
                or blob.strip() in ("container_widget", "container-widget")
                or "bottom" in blob):
            return "footer"
        if "nav" in blob or blob == "menu" or "navigation" in blob:
            return "menu"
        cur = cur.parent
    return None


def _default_region(heading):
    """Untuk heading bermodal transparansi APBDes tanpa region eksplisit."""
    cls = " ".join(heading.get("class") or [])
    if "catg_titile" in cls.lower():
        return "article"
    # titel pendek (widget/chart transparansi) -> bottom widget homepage
    words = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).split()
    if 2 <= len(words) <= 6:
        return "bottom"
    return "article"


APBDES_LOKASI_LABEL = {
    "menu": "Ditemukan pada Menu Navigasi",
    "sidebar": "Ditemukan pada Sidebar Widget",
    "footer": "Ditemukan pada Bottom Widget Homepage",
    "bottom": "Ditemukan pada Bottom Widget Homepage",
    "article": "Ditemukan pada Artikel",
}


def detect_apbdes_locations(base_url, html, links):
    """Scan variasi tata letak OpenSID untuk publikasi/grafik APBDes 2025 & 2026.

    Memeriksa: (1) bottom/footer widget transparansi, (2) sidebar widget,
    (3) artikel & menu navigasi. Mengembalikan
    (apbdes_2025, apbdes_2026, found_by_year) dg `found_by_year` memetakan
    tahun -> daftar label lokasi penemuan.
    """
    found_by_year = {"2025": [], "2026": []}
    if not html:
        return (False, False, found_by_year)
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return (False, False, found_by_year)
    soup = BeautifulSoup(html, "html.parser")

    def _record(yr, region, note=""):
        if yr in ("2025", "2026"):
            label = APBDES_LOKASI_LABEL.get(region, "Ditemukan pada Homepage")
            if note:
                label += " (%s)" % note
            if label not in found_by_year[yr]:
                found_by_year[yr].append(label)

    # (1) & (3) heading / title widget / artikel APBDes + tahun
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        t = re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()
        if not t:
            continue
        low = t.lower()
        if "apbdes" not in low and "realisasi" not in low and "transparansi" not in low:
            continue
        yr = _apbdes_year_from_text(low)
        if yr not in ("2025", "2026"):
            continue
        region = _dom_region(h) or _default_region(h)
        _record(yr, region, t[:60])

    # (2) container widget eksplisit (id/class apbdes / transparansi)
    for tag in soup.find_all("div"):
        cls = " ".join(tag.get("class") or [])
        ids = tag.get("id") or ""
        blob = (cls + " " + ids).lower()
        if "apbdes" not in blob and "transparansi" not in blob:
            continue
        txt = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        yr = _apbdes_year_from_text(txt.lower())
        if yr not in ("2025", "2026"):
            continue
        region = _dom_region(tag) or "bottom"
        _record(yr, region, "widget")

    # (3) menu navigasi -> tautan transparansi/keuangan/apbdes
    base_netloc = urlparse(base_url).netloc.lower()
    for a in soup.find_all("a"):
        href = a.get("href", "")
        at = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        blob = (at + " " + href).lower()
        if not any(k in blob for k in ["apbdes", "transparansi", "keuangan"]):
            continue
        yr = _apbdes_year_from_text(blob)
        if yr not in ("2025", "2026"):
            continue
        region = "menu"
        # jika menuju halaman artikel -> kategorikan artikel
        if re.search(r"/artikel/", href):
            region = "article"
        _record(yr, region, (at or href)[:60])

    return (bool(found_by_year["2025"]), bool(found_by_year["2026"]), found_by_year)



# ---- Kualitas berita 5W+1H ----
def assess_article_5w1h(text):
    """Perkiraan kelengkapan 5W+1H sebuah artikel. (What, Who, Where, When, Why, How)"""
    if not text or len(text) < 120:
        return 0
    low = text.lower()
    score = 0
    # When: tanggal
    if re.search(r"\d{1,2}\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+\d{4}", low) \
       or re.search(r"\d{4}-\d{2}-\d{2}", text):
        score += 1
    # Where: lokasi/kecamatan/desa/dusun/balai
    if re.search(r"(di|pada)\s+(dusun|desa|kecamatan|balai|lapangan|aula|kantor|rumah)", low) \
       or any(k in low for k in [" dusun ", " desa ", " kecamatan ", " jln ", " jalan "]):
        score += 1
    # Who: nama orang/jabatan formal
    if re.search(r"(kepala desa|kades|camat|bpd|ketua|lurah|bapak\s+[a-z]|ibu\s+[a-z]|saudara)", low) \
       or re.search(r"\b(tim|panitia|pemerintah|warga|masyarakat|perangkat)\b", low):
        score += 1
    # How (proses): kata kerja proses
    if re.search(r"(melakukan|melaksanakan|mengadakan|menggelar|digelar|dilaksanakan|dilakukan|menyelenggarakan)", low):
        score += 1
    # panjang isi (cukup substansi)
    if len(text) >= 300:
        score += 1
    # Why: tujuan/alasan
    if re.search(r"(dalam rangka|guna|tujuan|agar|untuk|bertujuan|dalam upaya)", low):
        score += 1
    return score


def main():
    with open(PESERTA_PATH, encoding="utf-8") as f:
        peserta = json.load(f)

    # resume
    out = {}
    if os.path.exists(OUT_PATH):
        try:
            with open(OUT_PATH, encoding="utf-8") as f:
                out = json.load(f)
        except Exception:
            out = {}

    for p in peserta:
        desa = p["desa"]
        url = p["url"]
        if desa in out and out[desa].get("done"):
            print(f"  {desa:22s} sudah, lewati")
            continue

        rec = {
            "done": False, "desa": desa, "url": url, "http_ok": False,
            "profile_pages_fetched": 0, "artikel_sample": [],
            "kuantitas_2026": 0,
            "sejarah_dan_visimisi": False,
            "sotk_struktur": False, "sotk_lembaga": False,
            "tupoksi_peta": False, "tupoksi_sinergi": False,
            "kualitas_berita": 0.0, "catatan": [],
            "apbdes_2025": False, "apbdes_2026": False, "apbdes_detail": [],
        }

        html = fetch(url)
        if not html:
            rec["catatan"].append("homepage gagal")
            out[desa] = rec
            print(f"  {desa:22s} GAGAL (no homepage)")
            continue
        rec["http_ok"] = True
        links = extract_links(url, html)

        # ---------- kumpulkan halaman profil (statis artikel) ----------
        # kategorikan link berdasarkan keyword slug
        profil_candidates = []
        art_2026 = {}  # path -> date, utk kuantitas
        for l in links:
            path = urlparse(l).path
            if re.search(r"/artikel/\d{4}/\d{1,2}/\d{1,2}/", path):
                d = article_date_from_path(path)
                if d and d.year == 2026 and 1 <= d.month <= 8:
                    art_2026[l] = d
            slug = strip_slug(l)
            if any(k in slug for k in ["sejarah", "visi", "misi", "profil-desa", "profil desa",
                                        "struktur", "sotk", "pemerintah-desa", "pemerintahan-desa",
                                        "perangkat", "aparatur", "lembaga", "bpd", "lpmd",
                                        "badan-permusyawaratan", "karang-taruna", "pkk",
                                        "data-desa", "data-wilayah", "peta", "wilayah",
                                        "sinergi", "rpjm"]):
                profil_candidates.append(l)
            if "/peta" in path or "data-wilayah" in path.lower():
                profil_candidates.append(l)

        # dedupe profil_candidates secara stabil, utamakan yang cocok banyak
        seen_p = set()
        dedup = []
        for l in profil_candidates:
            if l not in seen_p:
                seen_p.add(l)
                dedup.append(l)
        profil_candidates = dedup

        # fetch halaman profil terpilih (batas)
        text_blocks = []
        html_blocks = [html]
        slug_hits = []
        home_text = to_text(html)
        text_blocks.append(home_text)
        fetched = 0
        for l in profil_candidates[:MAX_PROFILE_PAGES]:
            ph = fetch(l)
            if ph:
                html_blocks.append(ph)
                text_blocks.append(to_text(ph))
                slug_hits.append(strip_slug(l))
                fetched += 1
            else:
                rec["catatan"].append("profil_page_gagal:" + urlparse(l).path[:40])
        rec["profile_pages_fetched"] = fetched

        # ---------- kualitas berita : sampel artikel 2026 ----------
        # urutkan artikel 2026 dari yang terbaru
        art_sorted = sorted(art_2026.items(), key=lambda kv: kv[1], reverse=True)
        sample_texts = []
        for l, d in art_sorted[:MAX_ARTIKEL_SAMPLE]:
            ah = fetch(l)
            if ah:
                t = to_text(ah)
                sample_texts.append(t)
                rec["artikel_sample"].append({
                    "url": l, "date": d.strftime("%Y-%m-%d"),
                    "awal": t[:160],
                })

        # ---------- klasifikasi komponen profil ----------
        join_home = " ".join([home_text])
        home_is_profil = bool(re.search(r"sejarah desa|visi dan misi|struktur organisasi|profil desa", home_text))
        rec["sejarah_dan_visimisi"] = check_sejarah_visimisi(text_blocks, slug_hits)
        rec["sotk_struktur"] = check_sotk_struktur(text_blocks, slug_hits)
        rec["sotk_lembaga"] = check_sotk_lembaga(text_blocks, slug_hits)
        rec["tupoksi_peta"] = check_tupoksi_peta(text_blocks, slug_hits, links)
        rec["tupoksi_sinergi"] = check_tupoksi_sinergi(text_blocks, slug_hits, html_blocks, url)

        # ---------- otentikasi: tandai konten DEFAULT OpenSID (Senggigi/Lombok) ----------
        default_hits = detect_default_content(text_blocks, slug_hits)
        for comp in default_hits:
            rec[comp] = False
        rec["konten_default"] = sorted(default_hits)
        if default_hits:
            rec["catatan"].append(
                "KONTEN DEFAULT OpenSID: " + ", ".join(sorted(default_hits)) +
                " masih terisi contoh bawaan 'Desa Senggigi (Lombok)', bukan konten desa "
                "(komponen tsb dianggap 0).")

        # ---------- kuantitas berita 2026 (Jan-Agu) ----------
        rec["kuantitas_2026"] = len(art_2026)

        # ---------- kualitas berita (rata-rata skor 5W+1H / 6, x10) ----------
        if sample_texts:
            raw_scores = [assess_article_5w1h(t) for t in sample_texts]
            avg_raw = sum(raw_scores) / len(raw_scores)
            rec["kualitas_berita"] = round(min(1.0, avg_raw / 6.0) * 10, 2)
            rec["berita_scores_raw"] = raw_scores

        # ---------- APBDes teliti (Realisasi 2025 & 2026) ----------
        a5, a6, a_detail = detect_apbdes(url, links)
        # APBDes yang dipublikasikan sebagai GAMBAR di galeri (mis. first/wilayah)
        g5 = g6 = False
        g_detail = []
        gal_pages = [html]
        for l in links:
            if "galeri" in urlparse(l).path or "/first/wilayah" in urlparse(l).path:
                gh = fetch(l)
                if gh:
                    gal_pages.append(gh)
                    break
        for ghtml in gal_pages:
            gg5, gg6, gd = detect_apbdes_gallery(url, links, ghtml)
            g5, g6 = g5 or gg5, g6 or gg6
            g_detail.extend(gd)
        # APBDes multi-lokasi: bottom/footer widget, sidebar, menu, artikel
        w5, w6, w_lokasi = detect_apbdes_locations(url, html, links)
        # gabungkan (artikel + galeri + widget lokasi) utk keputusan kelengkapan
        rec["apbdes_2025"] = a5 or g5 or w5
        rec["apbdes_2026"] = a6 or g6 or w6
        rec["apbdes_detail"] = a_detail + g_detail
        # Kumpulkan lokasi penemuan (artikel, galeri gambar, widget/sidebar/menu)
        lokasi = {"2025": set(w_lokasi["2025"]), "2026": set(w_lokasi["2026"])}
        for d in a_detail:
            if d.get("tahun") in ("2025", "2026"):
                lokasi[d["tahun"]].add("Ditemukan pada Artikel")
        for d in g_detail:
            if d.get("tahun") in ("2025", "2026"):
                lokasi[d["tahun"]].add("Ditemukan pada Galeri Gambar (upload/galeri/)")
        rec["apbdes_lokasi"] = {"2025": sorted(lokasi["2025"]),
                                "2026": sorted(lokasi["2026"])}

        rec["done"] = True
        out[desa] = rec
        print(f"  {desa:22s} sejarah={rec['sejarah_dan_visimisi']} "
              f"sotk={rec['sotk_struktur']} lembaga={rec['sotk_lembaga']} "
              f"peta={rec['tupoksi_peta']} sinergi={rec['tupoksi_sinergi']} "
              f"kuant26={rec['kuantitas_2026']} kual={rec['kualitas_berita']} "
              f"apb25={rec['apbdes_2025']} apb26={rec['apbdes_2026']}")

        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    print("\nSelesai. Hasil:", OUT_PATH)


if __name__ == "__main__":
    main()
