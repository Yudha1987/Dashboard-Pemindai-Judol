# -*- coding: utf-8 -*-
"""
Modul Web Scraping & Extraction khusus platform OpenSID:
- Mengambil halaman utama website desa (GET + timeout + User-Agent).
- Mengekstrak judul halaman, meta, teks body, dan daftar artikel terbaru
  beserta tanggal publikasi (format tanggal Indonesia/Inggris/ISO).
- Mengambil artikel terbaru dari Feed RSS OpenSID (endpoint /index.php/feed).
- Mengambil daftar URL halaman dalam dari sitemap OpenSID (/index.php/sitemap)
  untuk deep-scan.
- Mendeteksi apakah website memakai platform OpenSID.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config.config import RSS_PATHS, SITEMAP_PATHS, TIMEOUT

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

BODY_TEXT_LIMIT = 200_000

MONTHS_ID = {
    "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5,
    "juni": 6, "juli": 7, "agustus": 8, "september": 9, "oktober": 10,
    "november": 11, "desember": 12,
}

MONTHS_EN = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def fetch_page(url, timeout=None, verify=True):
    """Mengambil halaman; redirect diikuti otomatis."""
    return requests.get(
        url,
        timeout=timeout or TIMEOUT,
        headers=HEADERS,
        allow_redirects=True,
        verify=verify,
    )


def parse_date(text):
    """Mengurai teks tanggal menjadi objek datetime. None bila tidak dikenal."""
    if not text:
        return None
    s = str(text).strip()
    if not s:
        return None

    # ISO: 2026-08-12 / 2026/08/12 (+ waktu opsional)
    m = re.search(
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"
        r"(?:[T\s](\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        s,
    )
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Format: 12 Agustus 2026 / 12-agustus-2026 / 12. Agustus 2026
    m = re.search(r"(\d{1,2})[\s\-/.]{1,3}([A-Za-z]+)[\s\-/.]{1,3}(\d{4})", s)
    if m and m.group(2).lower() in MONTHS_ID:
        try:
            return datetime(int(m.group(3)), MONTHS_ID[m.group(2).lower()], int(m.group(1)))
        except ValueError:
            pass

    # Format Inggris: August 12, 2026 / August 12 2026
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS_EN:
        try:
            return datetime(int(m.group(3)), MONTHS_EN[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            pass

    # Format: 12/08/2026, 12-08-2026, 12.08.2026
    m = re.search(r"(\d{1,2})[\s\-/.]{1,3}(\d{1,2})[\s\-/.]{1,3}(\d{4})", s)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            try:
                return datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                pass

    # RFC 822 / RSS pubDate: "Wed, 12 Aug 2026 07:00:00 +0700"
    try:
        dt = parsedate_to_datetime(s)
        if dt:
            return dt.replace(tzinfo=None)
    except (TypeError, ValueError):
        pass

    return None


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_url_date(href):
    """Ekstrak tanggal dari URL berita (pola WordPress/Joomla).

    Mendukung:
      - /2026/07/30/slug-berita/            (year/month/day)
      - /2026/07/slug-berita/               (year/month)
      - /2026/30/07/slug-berita/            (day-first, bila 30<13 tak valid)
      - 2026/07/30 dalam path lain pun.
    """
    m = re.search(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$)", href or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            try:
                return datetime(int(m.group(1)), int(m.group(3)), int(m.group(2)))
            except ValueError:
                pass
    m = re.search(r"/(\d{4})/(\d{1,2})(?:/|$)", href or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            pass
    return None


def is_opensid(html):
    """Deteksi platform OpenSID dari HTML."""
    low = html[:200_000].lower()
    if "opensid" in low:
        return True
    m = re.search(r'<meta[^>]+name=["\']generator["\'][^>]*>', html[:200_000], re.I)
    if m and "opensid" in m.group(0).lower():
        return True
    return False


def detect_opensid_version(html):
    """Ekstrak versi OpenSID dari HTML (footer/meta). Kembalikan string atau None.

    Pola yang dikenali:
      - "OpenSID 2403.0.0" (footer — paling umum)
      - "OpenSID v25.01" / "OpenSID 25.01.0"
      - <meta name="generator" content="OpenSID 24.06">
    """
    low = html[:200_000]
    # Pola utama: "OpenSID YYMM.PATCH.MINOR"
    m = re.search(r'OpenSID\s+(\d{4}\.\d+\.\d+)', low, re.I)
    if m:
        return m.group(1)
    # Pola: "OpenSID v25.01" atau "OpenSID 25.01.0"
    m = re.search(r'OpenSID\s+v?(\d{2,4}\.\d+(?:\.\d+)?)', low, re.I)
    if m:
        return m.group(1)
    # Meta generator
    m = re.search(
        r'<meta[^>]+name=["\']generator["\'][^>]*content=["\']([^"\']+)["\']',
        low, re.I,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']generator["\']',
            low, re.I,
        )
    if m and "opensid" in m.group(1).lower():
        return m.group(1).strip()
    return None


def _is_post_link(href, base_url):
    """True jika href menunjuk ke artikel, bukan arsip/kategori/eksternal."""
    if not href:
        return False
    low = href.lower()
    if any(f in low for f in (
        "/category/", "/categories/", "/tag/", "/tags/", "/author/",
        "/wp-", "?cat=", "?page_id=", "wordpress.org", "javascript:",
        "/feed", "mailto:", "#",
    )):
        return False
    try:
        src = urlparse(href)
        base = urlparse(base_url)
    except ValueError:
        return True
    if src.scheme and src.netloc and src.netloc != base.netloc:
        return False
    path = (src.path or "").rstrip("/")
    if path == "" and (src.query or "") == "":
        return False
    if re.fullmatch(r"/\d{4}/\d{1,2}", path):
        return False
    return True


_DATE_CLASS_KEYS = (
    "date", "tanggal", "published", "post-date", "blog-date",
    "meta-date", "entry-date", "time", "artikel-tanggal", "meta",
)


def _find_date_in(el):
    time_el = el.find("time")
    if time_el is not None:
        return time_el.get("datetime") or time_el.get_text(strip=True)
    for key in _DATE_CLASS_KEYS:
        found = el.find(class_=lambda c: c and key in c.lower())
        if found is not None:
            txt = found.get_text(" ", strip=True)
            if txt:
                return txt
    # Fallback: tanggal ID/EN menyatu dalam teks ringkas (mis. Elementor:
    # "Ngawi, 1 September 2026 - DPRD ..."). Batasi panjang agar tak keliru.
    txt = el.get_text(" ", strip=True)
    if txt and len(txt) <= 400:
        for m in re.finditer(
            r"\d{1,2}(st|nd|rd|th)?[\s\-/.]{1,3}[A-Za-z]{3,}[\s\-/.]{1,3}\d{4}",
            txt,
        ):
            return m.group(0)
    return None


def _find_date(el):
    node = el
    for _ in range(3):
        if node is None:
            break
        text = _find_date_in(node)
        if text:
            return text
        node = node.parent
    return None


def _collect_posts(soup, base_url):
    """Mengumpulkan kandidat artikel lalu urutkan tanggal terbaru di depan."""
    candidates = []
    seen = {}

    def push(title, href, date_text):
        title = _clean(title)
        if len(title) < 3:
            return
        if not re.search(r"[A-Za-z]", title):
            return
        if not _is_post_link(href, base_url):
            return
        key = (href or title).lower()
        parsed_date = parse_date(date_text) or (_parse_url_date(href) if href else None)
        if key in seen:
            idx = seen[key]
            if candidates[idx]["date"] is None and parsed_date is not None:
                candidates[idx]["date"] = parsed_date
            return
        seen[key] = len(candidates)
        candidates.append({
            "title": title,
            "href": urljoin(base_url, href) if href else None,
            "date": parsed_date,
        })

    # Pendekatan 1: heading ber-link (umum di tema OpenSID/WP)
    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        a = h.find("a", href=True)
        if a is None:
            continue
        title = _clean(a.get_text()) or _clean(h.get_text())
        push(title, a["href"], _find_date(h.parent))

    # Pendekatan 2: container artikel umum OpenSID (.artikel, .post, dsb.)
    for sel in (".artikel", "article", ".post", ".entry", ".blog-item",
                ".news-item", ".berita-item", ".post-item", ".mg-post",
                ".blog-post", ".item"):
        for el in soup.select(sel):
            a = None
            for link in el.find_all("a", href=True):
                if len(_clean(link.get_text())) >= 15:
                    a = link
                    break
            if a is None:
                a = el.find("a", href=True)
            if a is None:
                continue
            heading = el.find(["h1", "h2", "h3", "h4", "h5"])
            title = ""
            if heading is not None:
                ha = heading.find("a", href=True)
                if ha is not None:
                    title = _clean(ha.get_text()) or _clean(heading.get_text())
            if not title:
                title = _clean(a.get_text())
            if not title:
                t = el.find(class_=lambda c: c and "title" in c.lower())
                title = _clean(t.get_text()) if t else ""
            push(title, a["href"], _find_date(el))

    # Pendekatan 3: <time datetime> lalu cari judul di sekitarnya
    for time_el in soup.find_all("time"):
        container = time_el.parent
        if container is None:
            continue
        container = container.parent or container
        a = container.find("a", href=True)
        h = container.find(["h1", "h2", "h3", "h4", "h5"])
        title = _clean(h.get_text()) if h else (_clean(a.get_text()) if a else "")
        push(title, a["href"] if a else None,
             time_el.get("datetime") or time_el.get_text(strip=True))

    dated = [c for c in candidates if c["date"]]
    undated = [c for c in candidates if not c["date"]]
    dated.sort(key=lambda c: c["date"], reverse=True)
    return dated + undated


def _collect_links(soup):
    """Kumpulkan semua nilai href/src (untuk deteksi link injection)."""
    values = []
    for a in soup.find_all("a", href=True):
        values.append(a["href"])
    for tag in ("iframe", "script", "img", "embed"):
        for el in soup.find_all(tag, attrs={"src": True}):
            values.append(el["src"])
    return " ".join(values)


def _collect_comments(soup):
    """Mengumpulkan teks komentar dari halaman artikel OpenSID.

    Pola yang dikenali:
      - div dengan class mengandung 'comment' / 'komentar'
      - list item dengan class 'comment'
      - div dengan id 'comments' / 'komentar'
    """
    comments = []
    seen = set()

    # Pola selector untuk section komentar
    selectors = [
        {"class": re.compile(r"comment-item|comment-body|komentar-item", re.I)},
        {"class": re.compile(r"^comment$", re.I)},
        {"id": re.compile(r"comments?|komentar", re.I)},
    ]

    for sel in selectors:
        for el in soup.find_all(["div", "li", "article"], **sel):
            text = el.get_text(" ", strip=True)
            if not text or len(text) < 10:
                continue
            # Buang jika hanya form/kirim komentar
            if re.search(r"kirim\s+komentar|nama\s+no\s+hp|isi\s+pesan", text, re.I):
                continue
            # Potong jika terlalu panjang
            text = text[:500]
            key = text[:100].lower()
            if key not in seen:
                seen.add(key)
                comments.append(text)

    return comments


def detect_comment_system(html, url=""):
    """Deteksi apakah situs memiliki sistem komentar aktif.

    Returns:
        dict: {
            "has_comments": bool,       # ada form komentar aktif
            "system": str,              # 'opensid', 'wordpress', 'unknown', None
            "akismet": bool,            # ada plugin Akismet
            "comment_admin_url": str,   # URL admin komentar (jika diketahui)
        }
    """
    result = {
        "has_comments": False,
        "system": None,
        "akismet": False,
        "comment_admin_url": "",
    }

    low = html[:200_000].lower()

    # Deteksi Akismet
    if "akismet" in low:
        result["akismet"] = True

    # Deteksi OpenSID comment form (prioritas — karena OpenSID juga punya form)
    if re.search(r'add_comment|group-komentar|kirim\s+komentar', low):
        result["has_comments"] = True
        result["system"] = "opensid"
        from urllib.parse import urlparse
        parsed = urlparse(url)
        result["comment_admin_url"] = "%s://%s/index.php/comment" % (parsed.scheme, parsed.netloc)

    # Deteksi WordPress comment form (hanya jika bukan OpenSID)
    elif re.search(r'wp-comments-post|id=["\']respond["\']|id=["\']commentform["\']', low):
        result["has_comments"] = True
        result["system"] = "wordpress"
        from urllib.parse import urlparse
        parsed = urlparse(url)
        result["comment_admin_url"] = "%s://%s/wp-admin/edit-comments.php" % (parsed.scheme, parsed.netloc)

    # Deteksi WordPress dari komponen khas WP (feed, REST API, wp-login)
    elif re.search(r'comments/feed|wp-json|wp-login\.php', low):
        result["system"] = "wordpress"
        from urllib.parse import urlparse
        parsed = urlparse(url)
        result["comment_admin_url"] = "%s://%s/wp-admin/edit-comments.php" % (parsed.scheme, parsed.netloc)

    return result


def extract_content(html, base_url):
    """Mengekstrak elemen penting dari HTML halaman."""
    soup = BeautifulSoup(html, "html.parser")

    title = _clean(soup.title.get_text()) if soup.title else ""
    meta_desc = ""
    og_title = ""
    if soup.find("meta", attrs={"name": "description"}):
        meta_desc = (soup.find("meta", attrs={"name": "description"})
                     .get("content", "") or "").strip()
    if soup.find("meta", attrs={"property": "og:title"}):
        og_title = (soup.find("meta", attrs={"property": "og:title"})
                    .get("content", "") or "").strip()

    h1 = _clean(soup.find("h1").get_text()) if soup.find("h1") else ""

    body_text = ""
    body = soup.find("body")
    if body is not None:
        body_text = _clean(body.get_text(" "))[:BODY_TEXT_LIMIT]

    posts = _collect_posts(soup, base_url)
    links = _collect_links(soup)
    comments = _collect_comments(soup)

    return {
        "title": title,
        "meta_description": meta_desc,
        "og_title": og_title,
        "h1": h1,
        "body_text": body_text,
        "posts": posts,
        "links": links,
        "comments": comments,
    }


def _parse_rss(content):
    """Parse RSS 2.0, ambil SEMUA item (terbaru lebih dulu).

    Returns:
        list of dict: [{"title", "href", "date"}] — item RSS mentah.
    """
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError):
        return []
    items = []
    for item in root.iter():
        tag = (item.tag.split("}")[-1]).lower()
        if tag != "item":
            continue
        title = None
        link = None
        pub_date = None
        for child in item:
            ctag = child.tag.split("}")[-1].lower()
            if ctag == "title":
                title = _clean(child.text)
            elif ctag == "link":
                link = (child.text or "").strip()
            elif ctag == "pubdate":
                pub_date = child.text
            elif ctag == "date":  # dc:date
                if pub_date is None:
                    pub_date = child.text
        if not title:
            continue
        items.append({
            "title": title,
            "href": link,
            "date": parse_date(pub_date),
        })
    return items


_FEED_LINK_RE = re.compile(
    r'<link\b[^>]*?type=["\']application/rss\+xml["\'][^>]*?>',
    re.IGNORECASE,
)


def _feed_href_from_html(html, base_url):
    """Ambil href feed RSS dari <link rel="alternate" type="application/rss+xml">."""
    if not html:
        return None
    for m in _FEED_LINK_RE.finditer(html[:200_000]):
        tag = m.group(0)
        rel = re.search(r'rel=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if rel and "alternate" not in rel.group(1).lower():
            continue
        href = re.search(r'href=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if href:
            value = href.group(1)
            return value if value.startswith("http") else urljoin(base_url + "/", value)
    return None


def get_feed(base_url, html=None):
    """Coba endpoint Feed RSS OpenSID; kembalikan daftar item (terbaru dulu).

    Mengembalikan list of dict (bukan item tunggal) agar deteksi
    postingan-berulang bisa memakai hingga 50+ artikel terbaru.
    """
    base = base_url.rstrip("/")
    candidates = []
    feed_href = _feed_href_from_html(html, base_url)
    if feed_href:
        candidates.append(feed_href)
    candidates.extend(base + path for path in RSS_PATHS)
    tried = set()
    for url in candidates:
        if url in tried:
            continue
        tried.add(url)
        try:
            resp = fetch_page(url)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        items = _parse_rss(resp.content)
        if items:
            return items
    return []


def _parse_sitemap(content):
    """Parse XML sitemap -> (root_tag, [locs])."""
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError):
        return "", []
    tag = root.tag.split("}")[-1].lower()
    locs = []
    for el in root.iter():
        if el.tag.split("}")[-1] == "loc" and el.text:
            locs.append(el.text.strip())
    return tag, locs


def _sitemap_urls(sitemap_url, visited=None, max_urls=None):
    if visited is None:
        visited = set()
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)
    try:
        resp = fetch_page(sitemap_url)
    except requests.RequestException:
        return []
    if resp.status_code != 200:
        return []

    tag, locs = _parse_sitemap(resp.content)
    if not locs:
        return []

    urls = []
    if tag == "sitemapindex":
        for loc in locs:
            urls.extend(_sitemap_urls(loc, visited, max_urls))
    else:
        urls.extend(locs)

    seen = set()
    result = []
    for u in urls:
        if u in seen or not u.lower().startswith(("http://", "https://")):
            continue
        seen.add(u)
        result.append(u)
        if max_urls and len(result) >= max_urls:
            break
    return result


def get_sitemap_urls(base_url, max_urls=None):
    """Cari sitemap OpenSID dan kembalikan daftar URL halaman dalam."""
    base = base_url.rstrip("/")
    for path in SITEMAP_PATHS:
        urls = _sitemap_urls(base + path, max_urls=max_urls)
        if urls:
            return urls
    return []
