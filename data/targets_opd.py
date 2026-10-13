# -*- coding: utf-8 -*-
"""
Daftar target website OPD, Kecamatan, Puskesmas, dan instansi lain
Kabupaten Ngawi (domain *.ngawikab.go.id) — total 76 target.

Nama otomatis diambil dari subdomain pertama (misal: bkpsdm -> BKPSDM),
kecuali yang didefinisikan eksplisit (Puskesmas & lainnya).
"""

from urllib.parse import urlparse

OPD_URLS = [
    "https://bkpsdm.ngawikab.go.id",
    "https://kesbang.ngawikab.go.id",
    "https://bakeu.ngawikab.go.id",
    "https://bpbd.ngawikab.go.id",
    "https://bapperida.ngawikab.go.id",
    "http://dukcapil.ngawikab.go.id/",
    "https://kesehatan.ngawikab.go.id",
    "https://dinkop.ngawikab.go.id",
    "https://dlh.ngawikab.go.id",
    "https://dpp.ngawikab.go.id",
    "https://disparpora.ngawikab.go.id",
    "https://dpmd.ngawikab.go.id",
    "https://dp3akb.ngawikab.go.id",
    "https://dpmptsp.ngawikab.go.id",
    "https://pendidikan.ngawikab.go.id",
    "https://dpptk.ngawikab.go.id",
    "https://dishub.ngawikab.go.id",
    "https://perpus.ngawikab.go.id",
    "https://pertanian.ngawikab.go.id",
    "https://dprkp.ngawikab.go.id",
    "https://pupr.ngawikab.go.id",
    "https://dinsos.ngawikab.go.id",
    "https://inspektorat.ngawikab.go.id",
    "https://satpolpp.ngawikab.go.id",
    "https://setda.ngawikab.go.id",
    "https://kominfo.ngawikab.go.id",
    "https://dprd.ngawikab.go.id",
]

KECAMATAN_URLS = [
    "https://bringin.ngawikab.go.id",
    "https://geneng.ngawikab.go.id",
    "https://gerih.ngawikab.go.id",
    "https://jogorogo.ngawikab.go.id",
    "https://karanganyar.ngawikab.go.id",
    "https://karangjati.ngawikab.go.id",
    "https://kasreman.ngawikab.go.id",
    "https://kedunggalar.ngawikab.go.id",
    "https://kendal.ngawikab.go.id",
    "https://kwadungan.ngawikab.go.id",
    "https://mantingan.ngawikab.go.id",
    "https://ngawi.ngawikab.go.id",
    "https://ngrambe.ngawikab.go.id",
    "https://padas.ngawikab.go.id",
    "https://pangkur.ngawikab.go.id",
    "https://paron.ngawikab.go.id",
    "https://pitu.ngawikab.go.id",
    "https://sine.ngawikab.go.id",
    "https://widodaren.ngawikab.go.id",
]

# Instansi lain (termasuk RS): format (nama, url)
LAINNYA = [
    ("Portal Ngawi", "https://ngawikab.go.id"),
    ("Kejari Ngawi", "https://kejari-ngawi.go.id"),
    ("Suara Ngawi", "https://suara.ngawikab.go.id"),
    ("PMI Ngawi", "https://pmi.ngawikab.go.id"),
    ("RSUD Dr. Soeroto", "https://rssoeroto.ngawikab.go.id"),
    ("PDAM Ngawi", "https://pdam.ngawikab.go.id"),
]

# Format: (nama, url)
PUSKESMAS = [
    ("Puskesmas Sine", "https://pkmsine.ngawikab.go.id"),
    ("Puskesmas Ngrambe", "https://pkmngrambe.ngawikab.go.id"),
    ("Puskesmas Jogorogo", "https://pkmjogorogo.ngawikab.go.id"),
    ("Puskesmas Kendal", "https://pkmkendal.ngawikab.go.id"),
    ("Puskesmas Geneng", "https://pkmgeneng.ngawikab.go.id"),
    ("Puskesmas Widodaren", "https://pkmwidodaren.ngawikab.go.id"),
    ("Puskesmas Kwadungan", "https://pkmkwadungan.ngawikab.go.id"),
    ("Puskesmas Pangkur", "https://pkmpangkur.ngawikab.go.id"),
    ("Puskesmas Karangjati", "https://pkmkarangjati.ngawikab.go.id"),
    ("Puskesmas Bringin", "https://pkmbringin.ngawikab.go.id"),
    ("Puskesmas Padas", "https://pkmpadas.ngawikab.go.id"),
    ("Puskesmas Kasreman", "https://pkmkasreman.ngawikab.go.id"),
    ("Puskesmas Ngawi", "https://pkmngawi.ngawikab.go.id"),
    ("Puskesmas Ngawi Purba", "https://pkmngawipurba.ngawikab.go.id"),
    ("Puskesmas Paron", "https://pkmparon.ngawikab.go.id"),
    ("Puskesmas Teguhan", "https://pkmteguhan.ngawikab.go.id"),
    ("Puskesmas Kedunggalar", "https://pkmkedunggalar.ngawikab.go.id"),
    ("Puskesmas Gemarang", "https://pkmgemarang.ngawikab.go.id"),
    ("Puskesmas Pitu", "https://pkmpitu.ngawikab.go.id"),
    ("Puskesmas Walikukun", "https://pkmwalikukun.ngawikab.go.id"),
    ("Puskesmas Kauman", "https://pkmkauman.ngawikab.go.id"),
    ("Puskesmas Mantingan", "https://pkmmantingan.ngawikab.go.id"),
    ("Puskesmas Tambakboyo", "https://pkmtambakboyo.ngawikab.go.id"),
    ("Puskesmas Karanganyar", "https://pkmkaranganyar.ngawikab.go.id"),
]

CATEGORY_ORDER = ["OPD", "KECAMATAN", "PUSKESMAS", "LAINNYA"]


def _derive_name(url):
    netloc = urlparse(url).netloc.lower()
    subdomain = netloc.split(".")[0]
    return subdomain.upper() if subdomain else netloc


def _build():
    targets = []
    for url in OPD_URLS:
        targets.append({"name": _derive_name(url), "url": url.rstrip("/"), "category": "OPD"})
    for url in KECAMATAN_URLS:
        targets.append({"name": _derive_name(url), "url": url.rstrip("/"), "category": "KECAMATAN"})
    for name, url in PUSKESMAS:
        targets.append({"name": name.upper(), "url": url.rstrip("/"), "category": "PUSKESMAS"})
    for name, url in LAINNYA:
        targets.append({"name": name.upper(), "url": url.rstrip("/"), "category": "LAINNYA"})
    return targets


TARGETS = _build()
