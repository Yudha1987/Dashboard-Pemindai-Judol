# -*- coding: utf-8 -*-
"""Tes deteksi otomatis perpindahan domain desa.id -> kabngawi.id."""

import unittest
from unittest import mock

import data.targets as targets
from data.targets import resolve_url
from src import scanner


class FakeResponse:
    def __init__(self, text, status_code=200, url="https://contoh.kabngawi.id/"):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}


def _target(key, name, kecamatan):
    old = "https://%s.desa.id" % key
    return {
        "name": name,
        "url": old,
        "url_lama": old,
        "fallback_urls": [],
        "domain": "desa.id",
        "domain_migrated": False,
        "category": "DESA",
        "kecamatan": kecamatan,
    }


class TestMigrationCandidates(unittest.TestCase):
    def test_simple_key_only_uses_exact_host(self):
        self.assertEqual(scanner._migration_candidates("hargosari"),
                         ["hargosari.kabngawi.id"])

    def test_key_with_suffix_also_tries_short_name(self):
        self.assertEqual(scanner._migration_candidates("babadan-paron"),
                         ["babadan-paron.kabngawi.id",
                          "babadan.kabngawi.id"])

    def test_tokens_include_kecamatan_for_suffixed_key(self):
        target = _target("babadan-paron", "Babadan Paron", "Paron")
        self.assertEqual(scanner._migration_tokens(target, "babadan-paron"),
                         ["babadan", "paron"])

    def test_tokens_simple_key_only_village_name(self):
        target = _target("hargosari", "Hargosari", "Sine")
        self.assertEqual(scanner._migration_tokens(target, "hargosari"),
                         ["hargosari"])


class TestMigrationPageValidation(unittest.TestCase):
    def test_valid_opensid_page(self):
        resp = FakeResponse(
            "<html><head><title>Website Resmi Desa Babadan "
            "Kecamatan Paron</title></head><body>OpenSID</body></html>",
            url="https://babadan.kabngawi.id/",
        )
        self.assertTrue(scanner._is_migration_page(
            resp, "babadan.kabngawi.id", ["babadan", "paron"]))

    def test_wrong_village_is_rejected(self):
        resp = FakeResponse(
            "<html><body>Website Resmi Desa Babadan Kecamatan Ngrambe "
            "OpenSID</body></html>",
            url="https://babadan.kabngawi.id/",
        )
        self.assertFalse(scanner._is_migration_page(
            resp, "babadan.kabngawi.id", ["babadan", "paron"]))

    def test_forbidden_page_is_rejected(self):
        resp = FakeResponse("<html><title>403 Forbidden</title></html>",
                            status_code=403,
                            url="https://babadan.kabngawi.id/")
        self.assertFalse(scanner._is_migration_page(
            resp, "babadan.kabngawi.id", ["babadan"]))

    def test_default_server_page_is_rejected(self):
        resp = FakeResponse(
            "<html><title>HTTP Server Test Page powered by "
            "CentOS-WebPanel.com</title></html>",
            url="https://babadan.kabngawi.id/",
        )
        self.assertFalse(scanner._is_migration_page(
            resp, "babadan.kabngawi.id", ["babadan"]))

    def test_landing_kominfo_is_rejected(self):
        resp = FakeResponse(
            "<html><title>Situs Dalam Pengawasan</title></html>",
            url="https://landing.domain.go.id?id=babadan.desa.id",
        )
        self.assertFalse(scanner._is_migration_page(
            resp, "babadan.kabngawi.id", ["babadan"]))


class TestMigrationRegistry(unittest.TestCase):
    def test_record_migration_used_by_resolve_url(self):
        key = "ujicoba-desa-baru"
        host = "ujicoba.kabngawi.id"
        try:
            self.assertTrue(targets.record_migration(key, host, persist=False))
            self.assertEqual(resolve_url("https://%s.desa.id" % key),
                             "https://" + host)
        finally:
            with targets._discovered_lock:
                targets._discovered_hosts.pop(key, None)

    def test_manual_mapping_never_overridden(self):
        self.assertFalse(targets.record_migration(
            "hargosari", "salah.kabngawi.id", persist=False))
        self.assertEqual(resolve_url("https://hargosari.desa.id"),
                         "https://hargosari.kabngawi.id")


class TestFetchTargetDetection(unittest.TestCase):
    def test_detects_new_domain_when_old_is_landing(self):
        target = _target("babadan-paron", "Babadan Paron", "Paron")
        landing = FakeResponse(
            "<html><title>Situs Dalam Pengawasan</title></html>",
            url="https://landing.domain.go.id?id=babadan-paron.desa.id",
        )
        forbidden = FakeResponse("<html>403 Forbidden</html>", status_code=403,
                                 url="https://babadan-paron.kabngawi.id/")
        valid = FakeResponse(
            "<html><head><title>Website Resmi Desa Babadan Kecamatan "
            "Paron</title></head><body>OpenSID</body></html>",
            url="https://babadan.kabngawi.id/",
        )

        def fake_fetch(url):
            if "babadan-paron.desa.id" in url:
                return landing
            if "babadan-paron.kabngawi.id" in url:
                return forbidden
            if "babadan.kabngawi.id" in url:
                return valid
            raise AssertionError("URL tak terduga: %s" % url)

        with mock.patch.object(scanner, "_fetch_with_retry", side_effect=fake_fetch), \
                mock.patch.object(scanner, "record_migration", return_value=True):
            resp, used_url, migrated_host = scanner._fetch_target(target)

        self.assertIs(resp, valid)
        self.assertEqual(used_url, "https://babadan.kabngawi.id")
        self.assertEqual(migrated_host, "babadan.kabngawi.id")

    def test_no_detection_when_old_site_is_healthy(self):
        target = _target("jururejo", "Jururejo", "Ngawi")
        healthy = FakeResponse(
            "<html><head><title>Website Resmi Desa Jururejo</title></head>"
            "<body>OpenSID</body></html>",
            url="https://jururejo.desa.id/",
        )
        with mock.patch.object(scanner, "_fetch_with_retry",
                               return_value=healthy) as fetch:
            resp, used_url, migrated_host = scanner._fetch_target(target)
        self.assertIs(resp, healthy)
        self.assertEqual(used_url, "https://jururejo.desa.id")
        self.assertIsNone(migrated_host)
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
