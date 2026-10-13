# -*- coding: utf-8 -*-

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.detector import analyze, detect_repeated_posts  # noqa: E402


def _extract(text, title="Desa Contoh", post_title="Pembangunan Jalan Desa"):
    return {
        "title": title,
        "og_title": "",
        "h1": "",
        "meta_description": "",
        "body_text": text,
        "posts": [{"title": post_title, "href": None, "date": None}],
        "last_post": {"title": post_title, "href": None, "date": None},
        "links": "",
    }


class TestDetector(unittest.TestCase):
    def test_clean_content_not_detected(self):
        extracted = _extract(
            "Warga desa bergotong royong membersihkan lingkungan setiap hari minggu."
        )
        result = analyze(extracted)
        self.assertFalse(result["matches"])
        self.assertFalse(result["critical"])

    def test_keyword_slot_detected(self):
        extracted = _extract("Kabar judi slot gacor gampang maxwin tersedia di sini.")
        result = analyze(extracted)
        keywords = {m["keyword"] for m in result["matches"]}
        self.assertTrue({"slot", "gacor", "maxwin"} & keywords)
        self.assertFalse(result["critical"])

    def test_keyword_link_alternatif_detected(self):
        extracted = _extract("Hubungi kami untuk link alternatif situs judi toto 4d.")
        result = analyze(extracted)
        keywords = {m["keyword"] for m in result["matches"]}
        self.assertIn("link alternatif", keywords)
        self.assertIn("situs judi", keywords)

    def test_keyword_toto_not_in_tutorial(self):
        # Word-boundary: "toto" tidak boleh cocok di dalam "tutorial".
        extracted = _extract("Simak tutorial memasak nasi liwet khas desa.")
        result = analyze(extracted)
        keywords = [m["keyword"] for m in result["matches"]]
        self.assertNotIn("toto", keywords)

    def test_thai_script_critical(self):
        extracted = _extract(
            "Pembaruan website",
            title="สล็อตเว็บตรง ฝากถอนไม่มีขั้นต่ำ",
        )
        result = analyze(extracted)
        self.assertTrue(result["critical"])
        self.assertTrue(any(m.get("foreign") for m in result["matches"]))

    def test_cyrillic_body_dominant_critical(self):
        text = " ".join(["казино слоты бонус"] * 30)
        extracted = _extract(text)
        result = analyze(extracted)
        self.assertTrue(result["critical"])

    def test_english_spam_keyword_detected(self):
        extracted = _extract("Promo online casino free spins no deposit bonus.")
        result = analyze(extracted)
        keywords = {m["keyword"] for m in result["matches"]}
        self.assertTrue({"online casino", "free spins", "no deposit bonus"} & keywords)

    def test_loan_spam_keyword_detected(self):
        extracted = _extract(
            "Tips Cara Membatalkan Pinjaman. Dapatkan pinjaman tanpa agunan, "
            "dana cair hari ini, no credit check loans cash advance."
        )
        result = analyze(extracted)
        keywords = {m["keyword"] for m in result["matches"]}
        categories = {m["category"] for m in result["matches"]}
        self.assertTrue(keywords & {
            "membatalkan pinjaman", "pinjaman tanpa agunan",
            "dana cair hari ini", "no credit check loans",
        })
        self.assertIn("Spam Pinjaman / Kredit", categories)
        # Permintaan admin: spam pinjaman ditandai sebagai serangan siber (critical).
        self.assertTrue(result["critical"])
        self.assertTrue(any(m.get("cyber") for m in result["matches"]))

    def test_loan_keyword_not_in_legit_content(self):
        # Kata polos tidak boleh false-positive terhadap aktivitas resmi desa.
        extracted = _extract(
            "Dana desa dialokasikan untuk pembangunan serta bantuan modal kredit "
            "usaha bagi warga, dengan proses pinjaman melalui BPD setempat."
        )
        result = analyze(extracted)
        keywords = [m["keyword"] for m in result["matches"]]
        self.assertNotIn("dana", keywords)
        self.assertNotIn("kredit", keywords)
        self.assertNotIn("pinjaman", keywords)

    def test_pinjol_awareness_article_not_detected(self):
        # Artikel sosialisasi resmi anti-pinjol memuat kata "pinjaman online"
        # dalam konteks edukasi — tidak boleh ditandai spam.
        extracted = _extract(
            "Sebagai upaya meningkatkan kesadaran masyarakat terhadap bahaya "
            "judi online dan pinjaman online ilegal, dilaksanakan kegiatan "
            "Sosialisasi Bahaya Pinjol dan Judol Ilegal di Aula Balai Desa."
        )
        result = analyze(extracted)
        self.assertFalse(result["matches"])
        self.assertFalse(result["critical"])

    def test_vietnamese_keyword_detected(self):
        extracted = _extract("Lihat kèo nhà cái terbaik dan nhà cái terpercaya.")
        result = analyze(extracted)
        keywords = {m["keyword"] for m in result["matches"]}
        self.assertTrue(keywords & {"nhà cái", "kèo nhà cái"})

    def test_repeated_posts_detected(self):
        # Run berurutan 10+ judul identik = spam.
        posts = [
            {"title": "Promo Pinjaman Cepat", "href": "/artikel/%d" % i,
             "date": None}
            for i in range(12)
        ] + [
            {"title": "Berita Desa Sehat", "href": "/artikel/d", "date": None},
        ]
        repeated = detect_repeated_posts(posts)
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["title"], "Promo Pinjaman Cepat")
        self.assertEqual(repeated[0]["count"], 12)

    def test_repeated_posts_min_count(self):
        posts = [
            {"title": "A", "href": "/artikel/a", "date": None},
            {"title": "A", "href": "/artikel/b", "date": None},
        ]
        repeated = detect_repeated_posts(posts)
        self.assertEqual(repeated, [])

    def test_repeated_posts_non_consecutive_not_flagged(self):
        # Duplikat judul TIDAK berurutan (widget/sidebar) bukan spam.
        posts = [
            {"title": "Berita Pembangunan Desa", "href": "/artikel/a", "date": None},
            {"title": "Berita Kegiatan Lain", "href": "/artikel/b", "date": None},
            {"title": "Berita Pembangunan Desa", "href": "/artikel/c", "date": None},
        ]
        repeated = detect_repeated_posts(posts)
        self.assertEqual(repeated, [])

    def test_repeated_posts_case_insensitive(self):
        # Judul sama dengan kapitalisasi/spasi berbeda tetap terhitung,
        # bila run-nya berurutan dan cukup panjang.
        posts = [
            {"title": "Agenda Rapat Desa", "href": "/artikel/a", "date": None},
            {"title": "agenda   rapat desa", "href": "/artikel/b", "date": None},
            {"title": "Agenda Rapat Desa", "href": "/artikel/c", "date": None},
        ] * 4
        repeated = detect_repeated_posts(posts, min_count=11)
        self.assertEqual(len(repeated), 1)
        self.assertEqual(repeated[0]["count"], 12)

    def test_repeated_posts_short_title_ignored(self):
        posts = [
            {"title": "Ab", "href": "/artikel/a", "date": None},
            {"title": "Ab", "href": "/artikel/b", "date": None},
        ]
        repeated = detect_repeated_posts(posts)
        self.assertEqual(repeated, [])

    def test_repeated_posts_unique_hrefs_kept(self):
        posts = [
            {"title": "Info Kegiatan", "href": "/artikel/x%d" % i, "date": None}
            for i in range(15)
        ]
        repeated = detect_repeated_posts(posts)
        self.assertEqual(len(repeated[0]["hrefs"]), 4)


if __name__ == "__main__":
    unittest.main()
