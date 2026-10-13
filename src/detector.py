# -*- coding: utf-8 -*-
"""
Modul Detektor: mencocokkan kata kunci judi online / slot / togel / spam SEO
& spam bahasa asing terhadap konten website desa OpenSID.

Sumber yang diperiksa:
  - Judul halaman (title / og:title / H1)
  - Meta description
  - Judul postingan terakhir
  - Teks body halaman
  - Nilai href/src (deteksi link injection)

Spam bahasa asing (spam injection / hack):
  - Karakter Thai [\u0E00-\u0E7F]
  - Karakter Cyrillic [\u0400-\u04FF]
  Satu karakter asing pun pada judul/meta/postingan sudah dicurigai; pada
  body perlu dominasi/rasio tertentu agar tidak false-positive.
"""

import re

from config.keywords import KEYWORDS, NON_LATIN_SCRIPTS

_ASCII_RX = re.compile(r"[A-Za-z0-9]")

# Run karakter base64 panjang (blob script/theme) memicu false-positive
# (mis. "slot", "toto", "judi" muncul acak di dalamnya). Buang sebelum scan.
_BASE64_RUN = re.compile(r"[A-Za-z0-9+/=]{60,}")


def _strip_noise(text):
    """Hapus run base64 panjang + ratakan spasi dari teks sumber."""
    if not text:
        return text
    text = _BASE64_RUN.sub(" ", text)
    return re.sub(r"\s+", " ", text)


def _kw_pattern(word):
    """Pola regex untuk satu kata kunci.

    Kata kunci Latin pendek/panjang memakai word-boundary (\\b) agar tidak
    false-positive (mis. "toto" tidak cocok di dalam "tutorial"). Kata kunci
    non-Latin (Thai, Vietnam beraksen, Cyrillic) tidak didukung \\b sehingga
    dicocokkan sebagai substring.
    """
    if _ASCII_RX.search(word):
        return re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
    return re.compile(re.escape(word))


def _build_sources(extracted):
    last_post = extracted.get("last_post") or (
        extracted["posts"][0] if extracted.get("posts") else None
    )
    raw = {
        "Judul Halaman": " ".join([
            extracted.get("title", ""),
            extracted.get("og_title", ""),
            extracted.get("h1", ""),
        ]),
        "Meta": extracted.get("meta_description", ""),
        "Postingan": last_post["title"] if last_post else "",
        "Body": extracted.get("body_text", ""),
        "Link/Referensi": extracted.get("links", ""),
    }
    return {k: _strip_noise(v) for k, v in raw.items()}


def scan_content(extracted, keyword_config=None):
    """Mengembalikan daftar kecocokan: [{keyword, category, source}]."""
    keyword_config = keyword_config or KEYWORDS
    sources = _build_sources(extracted)

    matched = []
    for category, words in keyword_config.items():
        for word in words:
            pattern = _kw_pattern(word)
            for source_name, text in sources.items():
                if text and pattern.search(text):
                    matched.append(
                        {"keyword": word, "category": category, "source": source_name}
                    )

    unique = []
    seen = set()
    for m in matched:
        key = (m["keyword"], m["source"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(m)
    return unique


def detect_foreign_scripts(extracted, scripts=None):
    """Deteksi aksara non-Latin Thai/Cyrillic pada konten website.

    Returns:
        list of dict: {script, label, source, count, sample}
    """
    scripts = scripts or NON_LATIN_SCRIPTS
    findings = []
    for spec in scripts:
        rx = re.compile(spec["regex"])
        for source_name, text in _build_sources(extracted).items():
            if not text:
                continue
            count = len(rx.findall(text))
            if not count:
                continue
            is_body = source_name == "Body"
            if is_body:
                letters = len(re.findall(r"\S", text)) or 1
                hit = (count / letters) >= 0.02 or count >= 40
            else:
                hit = True
            if not hit:
                continue
            m = rx.search(text)
            start = max(0, m.start() - 24)
            findings.append({
                "script": spec["id"],
                "label": spec["label"],
                "source": source_name,
                "count": count,
                "sample": text[start:m.end() + 24],
            })
    return findings


CRITICAL_LABEL = "CRITICAL: Terindikasi Spam Injection / Hack Bahasa Asing"

# Kategori yang dianggap serangan siber / spam prioritas tinggi (dinaikkan ke
# status CRITICAL agar segera ditindaklanjuti admin Kominfo). Cakupan: spam
# pinjaman/pinjol ilegal & spam injection bahasa asing.
CYBER_CATEGORIES = {"Spam Pinjaman / Kredit"}


REPEATED_POSTS_MIN = 10
REPEATED_POSTS_CRITICAL = 20


def _norm_title(title):
    return re.sub(r"\s+", " ", (title or "").strip().lower())


def detect_repeated_posts(posts, min_count=REPEATED_POSTS_MIN):
    """Deteksi indikasi spam: DERETAN postingan berada-urutan dengan judul
    sama (mis. spammer mem-publish 10-20 postingan beruntun bernarasi sama).

    Hanya postingan yang bekerja sebagai *run* (bersebelahan di daftar
    homepage) yang dihitung — duplikat 2x yang lahir dari widget/sidebar
    yang menautkan judul berita yang sama ke beberapa halaman TIDAK
    dianggap spam.

    Args:
        posts: list of dict {"title", "href", "date", ...}, sudah urut
            terbaru di depan (dari _collect_posts).
        min_count: panjang run (jumlah judul identik berurutan) minimum
            untuk dianggap spam/duplikat.

    Returns:
        list of dict: [{"title", "count", "hrefs"}], hanya run dengan
            count >= min_count.
    """
    found = []
    i = 0
    n = len(posts or [])
    while i < n:
        title = (posts[i].get("title") or "").strip()
        if len(title) < 3:
            i += 1
            continue
        key = _norm_title(title)
        j = i
        while (j + 1 < n and _norm_title(posts[j + 1].get("title")) == key
                and len((posts[j + 1].get("title") or "").strip()) >= 3):
            j += 1
        count = j - i + 1
        if count >= min_count:
            hrefs = []
            for p in posts[i:j + 1]:
                if p.get("href") and p["href"] not in hrefs and len(hrefs) < 4:
                    hrefs.append(p["href"])
            found.append({"title": title, "count": count, "hrefs": hrefs})
        i = j + 1
    return found


def scan_comments(comments, keyword_config=None):
    """Deteksi spam pada komentar. Kembalikan daftar komentar yang terindikasi spam.

    Returns:
        list of dict: [{text, matches, has_foreign}]
    """
    keyword_config = keyword_config or KEYWORDS
    spam_comments = []

    for comment_text in comments:
        text = _strip_noise(comment_text)
        if not text:
            continue

        # Cek kata kunci judi/spam
        matches = []
        for category, words in keyword_config.items():
            for word in words:
                pattern = _kw_pattern(word)
                if pattern.search(text):
                    matches.append({"keyword": word, "category": category})

        # Cek aksara asing (Thai/Cyrillic)
        has_foreign = False
        for spec in NON_LATIN_SCRIPTS:
            rx = re.compile(spec["regex"])
            if rx.search(text):
                has_foreign = True
                matches.append({
                    "keyword": "Aksara Asing (%s)" % spec["label"],
                    "category": "Spam Bahasa Asing",
                })
                break

        if matches or has_foreign:
            spam_comments.append({
                "text": comment_text[:200],
                "matches": matches,
                "has_foreign": has_foreign,
            })

    return spam_comments


def analyze(extracted, keyword_config=None):
    """Deteksi gabungan: kata kunci judi + spam bahasa asing.

    Returns:
        dict: {
            "matches": [...],   # kecocokan kata kunci (+ pseudo spam asing)
            "foreign": [...],   # detail deteksi aksara asing
            "critical": bool,   # True jika terindikasi spam injection/hack
        }
    """
    matches = scan_content(extracted, keyword_config)
    foreign = detect_foreign_scripts(extracted)
    critical = bool(foreign)

    # Naikkan ke CRITICAL bila ada kata kunci kategori serangan siber (mis.
    # spam pinjaman/pinjol ilegal) — bukan sekadar terindikasi judi/spam biasa.
    if any(m.get("category") in CYBER_CATEGORIES for m in matches):
        critical = True
        for m in matches:
            if m.get("category") in CYBER_CATEGORIES:
                m["cyber"] = True

    for i, f in enumerate(foreign):
        matches.insert(
            0,
            {
                "keyword": CRITICAL_LABEL if i == 0 else "\u26a0\ufe0f %s" % f["label"],
                "category": "Spam Bahasa Asing",
                "source": f["source"],
                "foreign": True,
                "script": f["script"],
            },
        )
    return {"matches": matches, "foreign": foreign, "critical": critical}
