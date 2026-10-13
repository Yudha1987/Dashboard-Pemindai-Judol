# -*- coding: utf-8 -*-
"""
Modul Scanner: orkestrasi scan satu website desa OpenSID.

Alur:
  1. Ambil halaman utama (retry untuk error jaringan intermiten).
  2. HTTP >= 400 (404/500/dll) atau timeout -> status OFFLINE, tanpa
     menghentikan pemindaian desa lain.
  3. Ekstrak konten & artikel terbaru dari homepage.
  4. Prioritas artikel terbaru dari Feed RSS OpenSID (/index.php/feed).
  5. Deteksi kata kunci judi/spam + aksara asing (Thai/Cyrillic).
  6. Deep-scan halaman dalam via sitemap OpenSID (opsional).
  7. Status: DETECTED / AMAN / OFFLINE.
"""

import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlparse

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from config.config import (
    RETRIES, RETRY_DELAY, TIMEOUT,
)
from src.detector import (
    CRITICAL_LABEL, REPEATED_POSTS_CRITICAL, analyze, detect_repeated_posts,
    scan_comments,
)
from src.scraper import (
    extract_content, fetch_page, get_feed, get_sitemap_urls, is_opensid,
    detect_opensid_version, detect_comment_system,
)

_audit_logger = logging.getLogger("audit_surat")
_audit_handler = logging.FileHandler("audit_surat.log", encoding="utf-8")
_audit_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
))
_audit_logger.addHandler(_audit_handler)
_audit_logger.setLevel(logging.DEBUG)


SURAT_AUDIT_RETRY = 3
SURAT_AUDIT_BACKOFF = 5

_SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
    ".pptx", ".mp4", ".mp3", ".wav", ".avi", ".mkv", ".css", ".js",
    ".json", ".xml", ".txt",
)


def _fetch_with_retry(url):
    last_exc = None
    for i in range(max(1, RETRIES + 1)):
        try:
            return fetch_page(url)
        except requests.exceptions.SSLError:
            try:
                urllib3.disable_warnings(InsecureRequestWarning)
                return fetch_page(url, verify=False)
            except Exception:
                pass
            raise
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            if i < RETRIES:
                time.sleep(RETRY_DELAY)
    raise last_exc


def _offline_reason(exc, http_status=None):
    if http_status is not None:
        return "Offline / Connection Timeout (HTTP %d)" % http_status
    if isinstance(exc, requests.exceptions.Timeout):
        return "Offline / Connection Timeout"
    if isinstance(exc, requests.exceptions.SSLError):
        return "Offline / Kesalahan sertifikat SSL"
    if isinstance(exc, requests.exceptions.ConnectionError):
        msg = str(exc)
        low = msg.lower()
        if "name or service not known" in low or "getaddrinfo" in low or "nodename" in low:
            return "Offline / DNS tidak ditemukan"
        if "connection refused" in low:
            return "Offline / Koneksi ditolak"
        if "timed out" in low or "timedout" in low:
            return "Offline / Connection Timeout"
        return "Offline / Koneksi gagal"
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return "Offline / Terlalu banyak redirect"
    return "Offline / %s" % (exc.__class__.__name__)


def _is_page_url(u, base):
    low = u.lower()
    if any(low.endswith(ext) for ext in _SKIP_EXT):
        return False
    if "/wp-content/uploads/" in low:
        return False
    if low.rstrip("/") == base.rstrip("/").lower():
        return False
    return True


def _scan_one_deep_page(page_url):
    try:
        resp = fetch_page(page_url)
        if resp.status_code >= 400:
            return None
        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype.lower() and not resp.text.strip().startswith("<"):
            return None
        extracted = extract_content(resp.text, page_url)
        analysis = analyze(extracted)
        return {
            "url": page_url,
            "matches": analysis["matches"],
            "foreign": analysis["foreign"],
            "critical": analysis["critical"],
        }
    except Exception:  # noqa: BLE001
        return None


def _deep_scan(url):
    """Deep-scan halaman dalam via sitemap OpenSID.

    Baca konfigurasi dari env saat dipanggil agar --no-deep-scan /
    --deep-scan-pages dari CLI berlaku (bukan nilai saat import).
    """
    agg = {"matches": [], "foreign": [], "critical": False}
    enabled = os.environ.get(
        "DEEP_SCAN_ENABLED", "1"
    ).strip().lower() not in ("0", "false", "no")
    try:
        pages = int(os.environ.get("DEEP_SCAN_PAGES", "20"))
    except ValueError:
        pages = 20
    try:
        threads = int(os.environ.get("DEEP_SCAN_THREADS", "3"))
    except ValueError:
        threads = 3
    if not enabled or pages <= 0:
        return agg

    page_urls = get_sitemap_urls(url, max_urls=pages)
    page_urls = [u for u in page_urls if _is_page_url(u, url)][:pages]
    if not page_urls:
        return agg

    with ThreadPoolExecutor(max_workers=max(1, threads)) as executor:
        futures = [executor.submit(_scan_one_deep_page, u) for u in page_urls]
        for future in as_completed(futures):
            res = future.result()
            if not res:
                continue
            for m in res["matches"]:
                m["page"] = res["url"]
                agg["matches"].append(m)
            for f in res["foreign"]:
                f["page"] = res["url"]
                agg["foreign"].append(f)
            agg["critical"] = agg["critical"] or res["critical"]
    return agg


def scan_target(target):
    url = target["url"]
    result = {
        "name": target["name"],
        "category": target["category"],
        "kecamatan": target.get("kecamatan", ""),
        "url": url,
        "status": "OFFLINE",
        "http_status": None,
        "error": None,
        "platform": None,
        "opensid_version": None,
        "comment_system": None,
        "spam_comments": [],
        "title": "",
        "last_post": None,
        "posts": [],
        "repeated_posts": [],
        "keywords": [],
        "foreign_scripts": [],
        "critical": False,
        "scanned_at": datetime.now(),
    }

    try:
        resp = _fetch_with_retry(url)
        result["http_status"] = resp.status_code

        if resp.status_code >= 400:
            if resp.status_code < 500:
                result["status"] = "OFFLINE"
                result["error"] = _offline_reason(None, resp.status_code)
                return result
            content_type = resp.headers.get("Content-Type", "")
            has_html = ("html" in content_type.lower()
                        or resp.text.strip().startswith("<"))
            if not has_html:
                result["status"] = "OFFLINE"
                result["error"] = _offline_reason(None, resp.status_code)
                return result

        content_type = resp.headers.get("Content-Type", "")
        if "html" not in content_type.lower() and not resp.text.strip().startswith("<"):
            result["status"] = "OFFLINE"
            result["error"] = "Respons bukan halaman HTML"
            return result

        html = resp.text
        result["platform"] = "OpenSID" if is_opensid(html) else "Website Lain"
        if result["platform"] == "OpenSID":
            result["opensid_version"] = detect_opensid_version(html)

        # Deteksi sistem komentar dari halaman utama (dulu)
        comment_info = detect_comment_system(html, url)

        extracted = extract_content(html, url)
        result["title"] = extracted["title"]
        result["posts"] = extracted["posts"]
        result["last_post"] = extracted["posts"][0] if extracted["posts"] else None

        # Deteksi spam: postingan berulang/duplikat dari daftar homepage.
        homepage_posts = extracted["posts"]

        # Prioritas artikel terbaru: Feed RSS OpenSID (daftar lengkap).
        feed_items = get_feed(url, html)
        if feed_items:
            # Deteksi spam beruntun memakai daftar feed (50+ artikel terbaru)
            # yang jauh lebih mencakup daripada homepage, sehingga deretan
            # ratusan postingan berjudul sama (mis. QLola/BRImo) terlihat.
            repeated = detect_repeated_posts(feed_items)
            result["repeated_posts"] = repeated
            # last_post = item ber-tanggal terbaru dari feed (bukan feed_items[0],
            # karena urutan XML belum tentu kronologis).
            dated_items = [i for i in feed_items if i.get("date")]
            if dated_items:
                feed_item = max(dated_items, key=lambda i: i["date"])
            else:
                feed_item = feed_items[0]
            extracted["posts"] = [feed_item]
            extracted["last_post"] = feed_item
            result["posts"] = [feed_item]
            result["last_post"] = feed_item
        else:
            repeated = detect_repeated_posts(homepage_posts)
            result["repeated_posts"] = repeated

        # Jika halaman utama tidak punya form komentar, cek artikel terbaru
        if not comment_info["has_comments"] and result.get("last_post"):
            art_url = result["last_post"].get("href", "")
            if art_url:
                try:
                    art_resp = fetch_page(art_url, timeout=6)
                    if art_resp and art_resp.status_code < 400:
                        comment_info = detect_comment_system(art_resp.text, art_url)
                except Exception:
                    pass
        result["comment_system"] = comment_info

        analysis = analyze(extracted)
        result["keywords"] = analysis["matches"]
        result["foreign_scripts"] = analysis["foreign"]
        result["critical"] = analysis["critical"]

        # Postingan berulang/duplikat -> indikasi spam (2+ judul sama).
        for dup in repeated:
            result["keywords"].append({
                "keyword": 'Postingan Berulang: "%s" (x%d)'
                           % (dup["title"][:60], dup["count"]),
                "category": "Spam Postingan Berulang",
                "source": "Postingan",
                "repeated": True,
                "count": dup["count"],
            })
            if dup["count"] >= REPEATED_POSTS_CRITICAL:
                result["critical"] = True

        # Deteksi spam pada komentar
        comments = extracted.get("comments", [])
        if comments:
            result["spam_comments"] = scan_comments(comments)

        # Deep-scan via sitemap agar judi/spam tersembunyi ikut terdeteksi.
        deep = _deep_scan(url)
        result["keywords"].extend(deep["matches"])
        result["foreign_scripts"].extend(deep["foreign"])
        result["critical"] = result["critical"] or deep["critical"]
        if deep["foreign"] and not any(m.get("foreign") for m in result["keywords"]):
            result["keywords"].insert(
                0,
                {
                    "keyword": CRITICAL_LABEL,
                    "category": "Spam Bahasa Asing",
                    "source": "Deep Scan (sitemap)",
                    "foreign": True,
                },
            )

        result["status"] = "DETECTED" if result["keywords"] else "AMAN"

    except requests.exceptions.Timeout:
        result["error"] = "Offline / Connection Timeout"
    except requests.exceptions.SSLError:
        result["error"] = "Offline / Kesalahan sertifikat SSL"
    except requests.exceptions.ConnectionError as e:
        result["error"] = _offline_reason(e)
    except requests.exceptions.TooManyRedirects:
        result["error"] = "Offline / Terlalu banyak redirect"
    except requests.exceptions.RequestException as e:
        result["error"] = "Offline / %s" % e.__class__.__name__
    except Exception as e:  # noqa: BLE001 - jaring pengaman
        result["error"] = "Offline / Kesalahan tidak terduga: %s" % e

    return result


# ---------------------------------------------------------------------------
# Audit & Validasi Data: jumlah_surat_tercetak
# ---------------------------------------------------------------------------

def verify_surat_count(domain_url, credentials=None, max_retries=None, backoff=None):
    """Verifikasi jumlah surat tercetak untuk satu desa.

    Dua metode fallback:
      1. Widget/Public check  -> GET /hom_sid tanpa login (widget tanpa auth).
      2. Login + widget check -> Login admin panel lalu baca widget.

    Args:
        domain_url: URL dasar desa (e.g. https://brangol.desa.id)
        credentials: dict {"user": str, "passwords": [str]} atau None
        max_retries: jumlah retry per metode (default SURAT_AUDIT_RETRY)
        backoff: jeda detik antar retry (default SURAT_AUDIT_BACKOFF)

    Returns:
        dict {
            "count": int | None,
            "scan_status": "VALID" | "VALID_ZERO" | "TIMEOUT" | "PENDING_AUDIT",
            "method": str,
            "http_status": int | None,
            "error": str | None,
            "retries_used": int,
        }
    """
    if max_retries is None:
        max_retries = SURAT_AUDIT_RETRY
    if backoff is None:
        backoff = SURAT_AUDIT_BACKOFF

    base = domain_url.rstrip("/")
    result = {
        "count": None,
        "scan_status": "PENDING_AUDIT",
        "method": "none",
        "http_status": None,
        "error": None,
        "retries_used": 0,
    }

    # --- Metode 1: Public widget check (tanpa login) ---
    count, http_status, error = _verify_widget_public(base, max_retries, backoff)
    result["retries_used"] += max_retries
    result["http_status"] = http_status

    if count is not None:
        result["count"] = count
        result["method"] = "widget_public"
        result["scan_status"] = "VALID" if count > 0 else "VALID_ZERO"
        result["error"] = error
        _audit_log(base, result)
        return result

    # --- Metode 2: Login + widget check ---
    if credentials:
        count, http_status, error = _verify_widget_login(
            base, credentials, max_retries, backoff
        )
        result["retries_used"] += max_retries
        if http_status:
            result["http_status"] = http_status

        if count is not None:
            result["count"] = count
            result["method"] = "widget_login"
            result["scan_status"] = "VALID" if count > 0 else "VALID_ZERO"
            result["error"] = error
            _audit_log(base, result)
            return result

    # --- Kedua metode gagal ---
    if error:
        result["error"] = error
    if result["scan_status"] == "PENDING_AUDIT":
        err_lower = (error or "").lower()
        if any(w in err_lower for w in (
            "timeout", "offline", "koneksi", "connection error",
            "max retries", "gagal", "ssl",
        )):
            result["scan_status"] = "TIMEOUT"

    _audit_log(base, result)
    return result


def _verify_widget_public(base, max_retries, backoff):
    """Metode 1: Ambil widget surat tanpa login."""
    for attempt in range(max_retries):
        try:
            resp = fetch_page(f"{base}/hom_sid")
            if resp.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    continue
                return None, resp.status_code, "HTTP %d" % resp.status_code

            if resp.status_code == 200 and "siteman" not in resp.url:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                count = _find_surat_count(soup)
                if count is not None:
                    return count, resp.status_code, None
                return 0, resp.status_code, None

            return None, resp.status_code, "Redirected to login"
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(backoff)
                continue
            return None, None, "Timeout"
        except requests.exceptions.SSLError:
            try:
                urllib3.disable_warnings(InsecureRequestWarning)
                resp = fetch_page(f"{base}/hom_sid", verify=False)
                if resp.status_code == 200 and "siteman" not in resp.url:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    count = _find_surat_count(soup)
                    if count is not None:
                        return count, resp.status_code, None
                    return 0, resp.status_code, None
                return None, resp.status_code, "SSL Error + fallback gagal"
            except Exception:
                return None, None, "SSL Error"
        except requests.exceptions.ConnectionError as e:
            msg = str(e).lower()
            if attempt < max_retries - 1:
                time.sleep(backoff)
                continue
            if "timed out" in msg:
                return None, None, "Connection Timeout"
            return None, None, "Connection Error: %s" % e.__class__.__name__
        except Exception as e:
            return None, None, "Error: %s" % e.__class__.__name__

    return None, None, "Max retries exceeded"


def _verify_widget_login(base, credentials, max_retries, backoff):
    """Metode 2: Login admin panel lalu baca widget surat."""
    from bs4 import BeautifulSoup

    user = credentials.get("user", "admin")
    passwords = credentials.get("passwords", [])

    for attempt in range(max_retries):
        try:
            session = _login_admin(base, user, passwords)
            if not session:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    continue
                return None, None, "Login gagal"

            for admin_path in ["/hom_sid", "/beranda"]:
                try:
                    resp = session.get(f"{base}{admin_path}", timeout=15)
                    if resp.status_code == 200 and "siteman" not in resp.url:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        count = _find_surat_count(soup)
                        if count is not None:
                            return count, resp.status_code, None
                        return 0, resp.status_code, None
                except Exception:
                    continue

            if attempt < max_retries - 1:
                time.sleep(backoff)
                continue
            return None, None, "Widget tidak ditemukan setelah login"

        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(backoff)
                continue
            return None, None, "Timeout"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(backoff)
                continue
            return None, None, "Error: %s" % e.__class__.__name__

    return None, None, "Max retries exceeded"


def _login_admin(base, user, passwords):
    """Login ke admin panel OpenSID."""
    for pw in passwords:
        try:
            s = requests.Session()
            s.verify = False
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            })
            r = s.get(f"{base}/siteman", timeout=10)
            if r.status_code != 200:
                continue
            csrf = s.cookies.get("sidcsrf", "")
            r = s.post(f"{base}/siteman/auth", data={
                "username": user, "password": pw, "sidcsrf": csrf,
            }, timeout=10, allow_redirects=True)
            if "siteman" in r.url and r.url.rstrip("/").endswith("siteman"):
                continue
            return s
        except Exception:
            continue
    return None


def _find_surat_count(soup):
    """Extract surat tercetak count from admin dashboard HTML."""
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


def _audit_log(url, result):
    """Catat hasil audit ke log file dan console."""
    status = result["scan_status"]
    count = result["count"]
    method = result["method"]
    error = result.get("error", "")
    retries = result.get("retries_used", 0)

    if status == "VALID_ZERO":
        _audit_logger.warning(
            "VALID_ZERO | %s | count=%s | method=%s | retries=%d | %s",
            url, count, method, retries, error or "OK"
        )
    elif status == "TIMEOUT":
        _audit_logger.error(
            "TIMEOUT | %s | count=%s | method=%s | retries=%d | %s",
            url, count, method, retries, error or "unknown"
        )
    elif status == "PENDING_AUDIT":
        _audit_logger.error(
            "PENDING_AUDIT | %s | count=%s | method=%s | retries=%d | %s",
            url, count, method, retries, error or "unknown"
        )
    else:
        _audit_logger.info(
            "VALID | %s | count=%s | method=%s | retries=%d | %s",
            url, count, method, retries, error or "OK"
        )
