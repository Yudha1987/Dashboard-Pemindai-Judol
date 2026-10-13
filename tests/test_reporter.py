# -*- coding: utf-8 -*-

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reporter import sort_results  # noqa: E402


def _result(name, status, critical=False, nkw=0, post_date=None):
    last = {"title": name, "href": None, "date": post_date} if post_date else None
    return {
        "name": name,
        "status": status,
        "critical": critical,
        "keywords": [{"keyword": "k%d" % i} for i in range(nkw)],
        "last_post": last,
    }


class TestReporter(unittest.TestCase):
    def test_detected_goes_to_top_when_no_date(self):
        results = [
            _result("Aman", "AMAN"),
            _result("Offline", "OFFLINE"),
            _result("Judi", "DETECTED", nkw=3),
        ]
        sorted_results = sort_results(results)
        self.assertEqual(sorted_results[0]["name"], "Judi")
        self.assertEqual(sorted_results[1]["name"], "Aman")
        self.assertEqual(sorted_results[2]["name"], "Offline")

    def test_latest_post_first_by_default(self):
        # Default: postingan terbaru tetap paling atas walau AMAN.
        results = [
            _result("Lama", "AMAN", post_date=datetime(2026, 1, 1)),
            _result("Terbaru", "AMAN", post_date=datetime(2026, 9, 1)),
        ]
        sorted_results = sort_results(results)
        self.assertEqual(sorted_results[0]["name"], "Terbaru")

    def test_latest_post_beats_detected(self):
        # Default sorts by recency, so a freshly-updated AMAN site is above
        # an old DETECTED site.
        results = [
            _result("Judi Lama", "DETECTED", nkw=2, post_date=datetime(2026, 1, 1)),
            _result("Aman Baru", "AMAN", post_date=datetime(2026, 9, 1)),
        ]
        sorted_results = sort_results(results)
        self.assertEqual(sorted_results[0]["name"], "Aman Baru")

    def test_critical_above_regular_detected_when_same_date(self):
        results = [
            _result("Judi Biasa", "DETECTED", nkw=2, post_date=datetime(2026, 9, 1)),
            _result("Spam Asing", "DETECTED", critical=True, nkw=1,
                    post_date=datetime(2026, 9, 1)),
        ]
        sorted_results = sort_results(results)
        self.assertEqual(sorted_results[0]["name"], "Spam Asing")
        self.assertEqual(sorted_results[1]["name"], "Judi Biasa")

    def test_more_keywords_above_fewer_when_same_date(self):
        results = [
            _result("Sedikit", "DETECTED", nkw=1, post_date=datetime(2026, 9, 1)),
            _result("Banyak", "DETECTED", nkw=5, post_date=datetime(2026, 9, 1)),
        ]
        sorted_results = sort_results(results)
        self.assertEqual(sorted_results[0]["name"], "Banyak")


if __name__ == "__main__":
    unittest.main()
