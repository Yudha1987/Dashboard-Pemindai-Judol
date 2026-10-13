# -*- coding: utf-8 -*-
"""
Konfigurasi pemindaian (bisa di-override lewat environment variable).
"""

import os


def _flag(name, default):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no")


CONCURRENCY = int(os.environ.get("CONCURRENCY", "10"))
TIMEOUT = int(os.environ.get("TIMEOUT", "25"))
RETRIES = int(os.environ.get("RETRIES", "2"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "3"))
REPORT_DIR = os.environ.get("REPORT_DIR", "output")

DEEP_SCAN_ENABLED = _flag("DEEP_SCAN_ENABLED", "1")
DEEP_SCAN_PAGES = int(os.environ.get("DEEP_SCAN_PAGES", "20"))
DEEP_SCAN_THREADS = int(os.environ.get("DEEP_SCAN_THREADS", "3"))

# Endpoint OpenSID
RSS_PATHS = ("/feed", "/index.php/feed", "/feed.xml", "/index.php/rss", "/rss.xml")
SITEMAP_PATHS = ("/index.php/sitemap", "/sitemap.xml", "/sitemap")
INDEX_FIRST = "/index.php/first"
