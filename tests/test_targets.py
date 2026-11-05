# -*- coding: utf-8 -*-
"""Tes pemetaan domain desa (desa.id -> kabngawi.id)."""

import unittest

from data.targets import (
    KABNGAWI_HOSTS, TARGETS, canonical_key, resolve_url,
)


class TestTargets(unittest.TestCase):
    def test_all_targets_have_unique_url(self):
        urls = [t["url"] for t in TARGETS]
        self.assertEqual(len(urls), len(set(urls)))

    def test_migrated_targets_use_kabngawi(self):
        migrated = [t for t in TARGETS if t["domain_migrated"]]
        self.assertEqual(len(migrated), len(KABNGAWI_HOSTS))
        for t in migrated:
            self.assertTrue(t["url"].endswith(".kabngawi.id"), t["url"])
            self.assertTrue(t["url_lama"].endswith(".desa.id"), t["url_lama"])
            self.assertIn(t["url_lama"], t["fallback_urls"])

    def test_non_migrated_targets_use_desa_id(self):
        for t in TARGETS:
            if not t["domain_migrated"]:
                self.assertTrue(t["url"].endswith(".desa.id"), t["url"])
                self.assertEqual(t["fallback_urls"], [])

    def test_resolve_url_accepts_old_and_new_domain(self):
        self.assertEqual(resolve_url("https://hargosari.desa.id"),
                         "https://hargosari.kabngawi.id")
        self.assertEqual(resolve_url("hargosari.kabngawi.id"),
                         "https://hargosari.kabngawi.id")
        self.assertEqual(resolve_url("Bangunrejo"),
                         "https://bangunrejo.kabngawi.id")
        self.assertEqual(resolve_url("https://jururejo.desa.id"),
                         "https://jururejo.desa.id")

    def test_canonical_key_maps_new_subdomain_to_old_key(self):
        self.assertEqual(canonical_key("bangunrejo.kabngawi.id"),
                         "bangunrejo-ngawi")
        self.assertEqual(canonical_key("ngawi-purba.kabngawi.id"),
                         "ngawi-ngawi")


if __name__ == "__main__":
    unittest.main()
