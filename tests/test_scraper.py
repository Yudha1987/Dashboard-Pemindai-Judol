# -*- coding: utf-8 -*-

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import (_parse_rss, _parse_url_date, extract_content,  # noqa: E402
                         is_opensid, parse_date)


class TestScraper(unittest.TestCase):
    def test_parse_date_indonesian(self):
        self.assertEqual(parse_date("12 Agustus 2026"), datetime(2026, 8, 12))

    def test_parse_date_iso(self):
        self.assertEqual(parse_date("2026-08-12"), datetime(2026, 8, 12))

    def test_parse_date_dmy(self):
        self.assertEqual(parse_date("12/08/2026"), datetime(2026, 8, 12))

    def test_parse_date_rss_rfc822(self):
        self.assertEqual(
            parse_date("Wed, 12 Aug 2026 07:00:00 +0700"),
            datetime(2026, 8, 12, 7, 0),
        )

    def test_parse_date_english(self):
        self.assertEqual(parse_date("August 12, 2026"), datetime(2026, 8, 12))

    def test_is_opensid(self):
        self.assertTrue(is_opensid(
            '<meta name="generator" content="OpenSID" />'
        ))
        self.assertTrue(is_opensid("<html><body>Powered by OpenSID</body></html>"))
        self.assertFalse(is_opensid("<html><body>WordPress</body></html>"))

    def test_extract_content_finds_post(self):
        html = """
        <html><head><title>Desa Jururejo</title>
        <meta name="description" content="Portal Desa Jururejo"></head>
        <body>
          <div class="artikel">
            <h2 class="artikel-title"><a href="/index.php/artikel/read/2026/8/12/1/kabar">Kabar Desa Terbaru</a></h2>
            <div class="artikel-tanggal">12 Agustus 2026</div>
          </div>
          <div class="artikel">
            <h2 class="artikel-title"><a href="/index.php/artikel/read/2026/7/2/2/lama">Berita Lama</a></h2>
            <div class="artikel-tanggal">2 Juli 2026</div>
          </div>
        </body></html>
        """
        extracted = extract_content(html, "https://jururejo.desa.id")
        self.assertEqual(extracted["title"], "Desa Jururejo")
        self.assertEqual(extracted["meta_description"], "Portal Desa Jururejo")
        self.assertTrue(extracted["posts"])
        # Terbaru di urutan pertama
        first = extracted["posts"][0]
        self.assertEqual(first["title"], "Kabar Desa Terbaru")
        self.assertEqual(first["date"], datetime(2026, 8, 12))

    def test_parse_url_date_wp_pattern(self):
        self.assertEqual(
            _parse_url_date("https://dinsos.ngawikab.go.id/2026/07/30/slug-berita/"),
            datetime(2026, 7, 30),
        )
        self.assertEqual(
            _parse_url_date("/2026/07/slug-bulanan/"),
            datetime(2026, 7, 1),
        )
        self.assertEqual(_parse_url_date("/artikel/read/2026/8/12/catat"),
                         datetime(2026, 8, 12))
        self.assertIsNone(_parse_url_date("/tentang-kami"))

    def test_parse_rss(self):
        rss = """<?xml version="1.0"?>
        <rss version="2.0"><channel><title>Feed Desa</title>
        <item>
          <title>Pengumuman Rapat Desa</title>
          <link>https://x.desa.id/index.php/artikel/read/99</link>
          <pubDate>Wed, 12 Aug 2026 07:00:00 +0700</pubDate>
        </item>
        </channel></rss>"""
        items = _parse_rss(rss.encode("utf-8"))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "Pengumuman Rapat Desa")
        self.assertEqual(item["href"], "https://x.desa.id/index.php/artikel/read/99")
        self.assertEqual(item["date"], datetime(2026, 8, 12, 7, 0))


if __name__ == "__main__":
    unittest.main()
