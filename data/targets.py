# -*- coding: utf-8 -*-
"""
Daftar target website Desa (.desa.id) Kabupaten Ngawi — platform OpenSID.

Daftar ini adalah daftar otoritatif dari pengelola (212 entri; 211 unik
setelah deduplikasi). Entri baru dapat ditambahkan langsung ke RAW_HOSTS
(satu per baris). Nama desa otomatis diambil dari nama host, kecuali yang
didefinisikan di NAME_OVERRIDES.
"""

import re

RAW_HOSTS = """https://jururejo.desa.id
https://sumberbening.desa.id
https://rejuno.desa.id
https://gemarang.desa.id
https://walikukun.desa.id
https://pakah.desa.id
https://karangjati-ngawi.desa.id
https://majasem.desa.id
https://karangtengahprandon.desa.id
https://sidokerto-ngawi.desa.id
https://tambakboyo-ngawi.desa.id
https://rejomulyo.desa.id
https://selopuro.desa.id
https://brangol.desa.id
https://kendal-ngawi.desa.id
https://jaten.desa.id
https://banyuurip-ngawi.desa.id
https://krompol.desa.id
https://bringin-ngawi.desa.id
https://pengkol.desa.id
https://wonokerto-ngawi.desa.id
https://legowetan.desa.id
https://watualang.desa.id
https://karangmalang-ngawi.desa.id
https://babadan-pangkur.desa.id
https://kedungprahu.desa.id
https://karangasri.desa.id
https://sukowiyono.desa.id
https://wakah.desa.id
https://ngawi-ngawi.desa.id
https://sumber-ngawi.desa.id
https://jatimulyo-ngawi.desa.id
https://dampit-ngawi.desa.id
https://dero.desa.id
https://gandong.desa.id
https://jatipuro.desa.id
https://sekarjati.desa.id
https://campurasri.desa.id
https://kartoharjo.desa.id
https://keraskulon.desa.id
https://karanggeneng-ngawi.desa.id
https://banyubiru-ngawi.desa.id
https://wonosari-ngawi.desa.id
https://sumbersari-ngawi.desa.id
https://budug-ngawi.desa.id
https://beran.desa.id
https://paras-ngawi.desa.id
https://keraswetan.desa.id
https://cepoko.desa.id
https://pandansari-ngawi.desa.id
https://cangakan.desa.id
https://mangunharjo-ngawi.desa.id
https://wonorejo-ngawi.desa.id
https://karangrejo-ngawi.desa.id
https://kalang.desa.id
https://dawung.desa.id
https://pelangkidul.desa.id
https://karangsono-ngawi.desa.id
https://gunungsari-ngawi.desa.id
https://mantingan-ngawi.desa.id
https://pocol.desa.id
https://suruh.desa.id
https://papungan.desa.id
https://bangunrejolor.desa.id
https://grudo.desa.id
https://jatirejo-ngawi.desa.id
https://gandri-ngawi.desa.id
https://girikerto-ngawi.desa.id
https://guyung.desa.id
https://kasreman.desa.id
https://keniten-ngawi.desa.id
https://klitik.desa.id
https://sembung-ngawi.desa.id
https://pangkur.desa.id
https://kersoharjo.desa.id
https://randusongo.desa.id
https://kawu.desa.id
https://katikan.desa.id
https://geneng-ngawi.desa.id
https://kersikan.desa.id
https://sidomakmur-ngawi.desa.id
https://sekarputih-ngawi.desa.id
https://dungmiri.desa.id
https://padas.desa.id
https://sidorejo-geneng.desa.id
https://legundi.desa.id
https://paron.desa.id
https://kedunggudel.desa.id
https://patalan.desa.id
https://karanggupito.desa.id
https://ngrambe-ngawi.desa.id
https://ngancar.desa.id
https://sumberejo-ngawi.desa.id
https://sidolaju.desa.id
https://manisharjo.desa.id
https://manisharjo.desa.id
https://jambangan-ngawi.desa.id
https://jogorogo.desa.id
https://gempol.desa.id
https://tawun.desa.id
https://pleset.desa.id
https://babadan-paron.desa.id
https://dumplengan.desa.id
https://cantel.desa.id
https://hargosari.desa.id
https://dempel.desa.id
https://ploso.desa.id
https://banget.desa.id
https://kedungharjo.desa.id
https://banjaransari.desa.id
https://girimulyo.desa.id
https://talang.desa.id
https://kiyonten.desa.id
https://kwadunganlor.desa.id
https://bintoyo.desa.id
https://pohkonyal.desa.id
https://gentong-ngawi.desa.id
https://kedungputri.desa.id
https://ketanggung.desa.id
https://plosolor.desa.id
https://ringinanom.desa.id
https://sumengko.desa.id
https://ngompro.desa.id
https://waruktengah.desa.id
https://sine.desa.id
https://tepas-ngawi.desa.id
https://ngrayudan.desa.id
https://pandean.desa.id
https://sriwedari-ngawi.desa.id
https://sidorejo-karangjati.desa.id
https://begal.desa.id
https://sambirejo-ngrambe.desa.id
https://tungkulrejo.desa.id
https://semen.desa.id
https://banjarbanggi.desa.id
https://karangbanyu.desa.id
https://kayutrejo.desa.id
https://gendingan.desa.id
https://widodaren-gerih.desa.id
https://tanjungsari-ngawi.desa.id
https://mengger.desa.id
https://jenggrik.desa.id
https://dadapan-ngawi.desa.id
https://kandangan-ngawi.desa.id
https://giriharjo.desa.id
https://sambiroto-ngawi.desa.id
https://kebon.desa.id
https://sirigan.desa.id
https://gendol.desa.id
https://klampisan.desa.id
https://umbulrejo.desa.id
https://brubuh.desa.id
https://kletekan.desa.id
https://karanganyar-ngawi.desa.id
https://legokulon.desa.id
https://sidorejo-kendal.desa.id
https://warukkalong.desa.id
https://dinden.desa.id
https://mojomanis.desa.id
https://mendiro-ngawi.desa.id
https://bendo-ngawi.desa.id
https://gelung.desa.id
https://teguhan.desa.id
https://pitu.desa.id
https://ngrendeng.desa.id
https://sekaralas.desa.id
https://mojo-ngawi.desa.id
https://baderan.desa.id
https://kasreman-geneng.desa.id
https://macanan.desa.id
https://bangunrejo-ngawi.desa.id
https://puhti.desa.id
https://danguk.desa.id
https://pelanglor.desa.id
https://bangunrejokidul.desa.id
https://gayam-ngawi.desa.id
https://pojok-ngawi.desa.id
https://jenangan.desa.id
https://purwosari-ngawi.desa.id
https://kerek.desa.id
https://babadan-ngrambe.desa.id
https://pucangan.desa.id
https://pacing.desa.id
https://dawu.desa.id
https://tempuran-ngawi.desa.id
https://jagir.desa.id
https://kenongorejo.desa.id
https://tambakromo-geneng.desa.id
https://gerih.desa.id
https://soco.desa.id
https://gembol.desa.id
https://jatigembol.desa.id
https://kedunggalar.desa.id
https://simo-kendal.desa.id
https://kendung.desa.id
https://simo-kwadungan.desa.id
https://kwadungan.desa.id
https://tirak.desa.id
https://sambirejo-mantingan.desa.id
https://hargomulyo-ngawi.desa.id
https://krandegan-ngawi.desa.id
https://sidomulyo-ngawi.desa.id
https://tawangrejo-ngawi.desa.id
https://munggut.desa.id
https://tambakromo-padas.desa.id
https://ngale.desa.id
https://jeblogan.desa.id
https://tulakan-ngawi.desa.id
https://kauman-sine.desa.id
https://widodaren.desa.id
https://kauman-widodaren.desa.id
https://sawo-ngawi.desa.id
https://setono.desa.id
https://kuniran.desa.id"""

# Nama tampilan khusus (mis. host berisi spasi pada daftar asli).
NAME_OVERRIDES = {
    "waruktengah": "Waruk Tengah",
}

# Pemetaan host -> kecamatan (19 kecamatan, 213 desa; sumber: Permendagri /
# daftar resmi desa Kab. Ngawi). Dipakai untuk filter dashboard per kecamatan.
KECAMATAN_BY_HOST = {
    'babadan-ngrambe': 'Ngrambe',
    'babadan-pangkur': 'Pangkur',
    'babadan-paron': 'Paron',
    'baderan': 'Geneng',
    'banget': 'Kwadungan',
    'bangunrejo-ngawi': 'Karanganyar',
    'bangunrejokidul': 'Kedunggalar',
    'bangunrejolor': 'Pitu',
    'banjaransari': 'Padas',
    'banjarbanggi': 'Pitu',
    'banyubiru-ngawi': 'Widodaren',
    'banyuurip-ngawi': 'Ngawi',
    'begal': 'Kedunggalar',
    'bendo-ngawi': 'Padas',
    'beran': 'Ngawi',
    'bintoyo': 'Padas',
    'brangol': 'Karangjati',
    'bringin-ngawi': 'Bringin',
    'brubuh': 'Jogorogo',
    'budug-ngawi': 'Kwadungan',
    'campurasri': 'Karangjati',
    'cangakan': 'Kasreman',
    'cantel': 'Pitu',
    'cepoko': 'Ngrambe',
    'dadapan-ngawi': 'Kendal',
    'dampit-ngawi': 'Bringin',
    'danguk': 'Karangjati',
    'dawu': 'Paron',
    'dawung': 'Jogorogo',
    'dempel': 'Geneng',
    'dero': 'Bringin',
    'dinden': 'Kwadungan',
    'dumplengan': 'Pitu',
    'dungmiri': 'Karangjati',
    'gandong': 'Bringin',
    'gandri-ngawi': 'Pangkur',
    'gayam-ngawi': 'Kendal',
    'gelung': 'Paron',
    'gemarang': 'Kedunggalar',
    'gembol': 'Karanganyar',
    'gempol': 'Karangjati',
    'gendingan': 'Widodaren',
    'gendol': 'Sine',
    'geneng-ngawi': 'Geneng',
    'gentong-ngawi': 'Paron',
    'gerih': 'Gerih',
    'giriharjo': 'Ngrambe',
    'girikerto-ngawi': 'Sine',
    'girimulyo': 'Jogorogo',
    'grudo': 'Ngawi',
    'gunungsari-ngawi': 'Kasreman',
    'guyung': 'Gerih',
    'hargomulyo-ngawi': 'Ngrambe',
    'hargosari': 'Sine',
    'jagir': 'Sine',
    'jambangan-ngawi': 'Paron',
    'jaten': 'Jogorogo',
    'jatigembol': 'Kedunggalar',
    'jatimulyo-ngawi': 'Mantingan',
    'jatipuro': 'Karangjati',
    'jatirejo-ngawi': 'Kasreman',
    'jeblogan': 'Paron',
    'jenangan': 'Kwadungan',
    'jenggrik': 'Kedunggalar',
    'jogorogo': 'Jogorogo',
    'jururejo': 'Ngawi',
    'kalang': 'Pitu',
    'kandangan-ngawi': 'Ngawi',
    'karanganyar-ngawi': 'Karanganyar',
    'karangasri': 'Ngawi',
    'karangbanyu': 'Widodaren',
    'karanggeneng-ngawi': 'Pitu',
    'karanggupito': 'Kendal',
    'karangjati-ngawi': 'Karangjati',
    'karangmalang-ngawi': 'Kasreman',
    'karangrejo-ngawi': 'Kendal',
    'karangsono-ngawi': 'Kwadungan',
    'karangtengahprandon': 'Ngawi',
    'kartoharjo': 'Ngawi',
    'kasreman': 'Kasreman',
    'kasreman-geneng': 'Geneng',
    'katikan': 'Kedunggalar',
    'kauman-sine': 'Sine',
    'kauman-widodaren': 'Widodaren',
    'kawu': 'Kedunggalar',
    'kayutrejo': 'Widodaren',
    'kebon': 'Paron',
    'kedunggalar': 'Kedunggalar',
    'kedunggudel': 'Widodaren',
    'kedungharjo': 'Mantingan',
    'kedungprahu': 'Padas',
    'kedungputri': 'Paron',
    'kendal-ngawi': 'Kendal',
    'kendung': 'Kwadungan',
    'keniten-ngawi': 'Geneng',
    'kenongorejo': 'Bringin',
    'keraskulon': 'Gerih',
    'keraswetan': 'Geneng',
    'kerek': 'Ngawi',
    'kersikan': 'Geneng',
    'kersoharjo': 'Geneng',
    'ketanggung': 'Sine',
    'kiyonten': 'Kasreman',
    'klampisan': 'Geneng',
    'kletekan': 'Jogorogo',
    'klitik': 'Geneng',
    'krandegan-ngawi': 'Ngrambe',
    'krompol': 'Bringin',
    'kuniran': 'Sine',
    'kwadungan': 'Kwadungan',
    'kwadunganlor': 'Padas',
    'legokulon': 'Kasreman',
    'legowetan': 'Bringin',
    'legundi': 'Karangjati',
    'macanan': 'Jogorogo',
    'majasem': 'Kendal',
    'mangunharjo-ngawi': 'Ngawi',
    'manisharjo': 'Ngrambe',
    'mantingan-ngawi': 'Mantingan',
    'mendiro-ngawi': 'Ngrambe',
    'mengger': 'Karanganyar',
    'mojo-ngawi': 'Bringin',
    'mojomanis': 'Kwadungan',
    'munggut': 'Padas',
    'ngale': 'Paron',
    'ngancar': 'Pitu',
    'ngawi-ngawi': 'Ngawi',
    'ngompro': 'Pangkur',
    'ngrambe-ngawi': 'Ngrambe',
    'ngrayudan': 'Jogorogo',
    'ngrendeng': 'Sine',
    'pacing': 'Padas',
    'padas': 'Padas',
    'pakah': 'Mantingan',
    'pandansari-ngawi': 'Sine',
    'pandean': 'Karanganyar',
    'pangkur': 'Pangkur',
    'papungan': 'Pitu',
    'paras-ngawi': 'Pangkur',
    'paron': 'Paron',
    'patalan': 'Kendal',
    'pelangkidul': 'Kedunggalar',
    'pelanglor': 'Kedunggalar',
    'pengkol': 'Mantingan',
    'pitu': 'Pitu',
    'pleset': 'Pangkur',
    'ploso': 'Kendal',
    'plosolor': 'Karangjati',
    'pocol': 'Sine',
    'pohkonyal': 'Pangkur',
    'pojok-ngawi': 'Kwadungan',
    'pucangan': 'Ngrambe',
    'puhti': 'Karangjati',
    'purwosari-ngawi': 'Kwadungan',
    'randusongo': 'Gerih',
    'rejomulyo': 'Karangjati',
    'rejuno': 'Karangjati',
    'ringinanom': 'Karangjati',
    'sambirejo-mantingan': 'Mantingan',
    'sambirejo-ngrambe': 'Ngrambe',
    'sambiroto-ngawi': 'Padas',
    'sawo-ngawi': 'Karangjati',
    'sekaralas': 'Widodaren',
    'sekarjati': 'Karanganyar',
    'sekarputih-ngawi': 'Widodaren',
    'selopuro': 'Pitu',
    'sembung-ngawi': 'Karangjati',
    'semen': 'Paron',
    'setono': 'Ngrambe',
    'sidokerto-ngawi': 'Karangjati',
    'sidolaju': 'Widodaren',
    'sidomakmur-ngawi': 'Widodaren',
    'sidomulyo-ngawi': 'Ngrambe',
    'sidorejo-geneng': 'Geneng',
    'sidorejo-karangjati': 'Karangjati',
    'sidorejo-kendal': 'Kendal',
    'simo-kendal': 'Kendal',
    'simo-kwadungan': 'Kwadungan',
    'sine': 'Sine',
    'sirigan': 'Paron',
    'soco': 'Jogorogo',
    'sriwedari-ngawi': 'Karanganyar',
    'sukowiyono': 'Padas',
    'sumber-ngawi': 'Pangkur',
    'sumberbening': 'Bringin',
    'sumberejo-ngawi': 'Sine',
    'sumbersari-ngawi': 'Sine',
    'sumengko': 'Kwadungan',
    'suruh': 'Bringin',
    'talang': 'Jogorogo',
    'tambakboyo-ngawi': 'Mantingan',
    'tambakromo-geneng': 'Geneng',
    'tambakromo-padas': 'Padas',
    'tanjungsari-ngawi': 'Jogorogo',
    'tawangrejo-ngawi': 'Ngrambe',
    'tawun': 'Kasreman',
    'teguhan': 'Paron',
    'tempuran-ngawi': 'Paron',
    'tepas-ngawi': 'Geneng',
    'tirak': 'Kwadungan',
    'tulakan-ngawi': 'Sine',
    'tungkulrejo': 'Padas',
    'umbulrejo': 'Jogorogo',
    'wakah': 'Ngrambe',
    'walikukun': 'Widodaren',
    'warukkalong': 'Kwadungan',
    'waruktengah': 'Pangkur',
    'watualang': 'Ngawi',
    'widodaren': 'Widodaren',
    'widodaren-gerih': 'Gerih',
    'wonokerto-ngawi': 'Kedunggalar',
    'wonorejo-ngawi': 'Kedunggalar',
    'wonosari-ngawi': 'Sine',
}

# Urutan kecamatan untuk tombol filter dashboard.
KECAMATAN_ORDER = [
    "Bringin", "Geneng", "Gerih", "Jogorogo", "Karanganyar", "Karangjati",
    "Kasreman", "Kedunggalar", "Kendal", "Kwadungan", "Mantingan", "Ngawi",
    "Ngrambe", "Padas", "Pangkur", "Paron", "Pitu", "Sine", "Widodaren",
]


def _derive_name(host):
    name = host.split(".")[0]
    words = [w for w in re.split(r"[^a-zA-Z0-9]+", name) if w]
    return " ".join(w.capitalize() for w in words) or host


def _build():
    targets = []
    seen = set()
    for line in RAW_HOSTS.splitlines():
        host = (line or "").strip()
        if not host:
            continue
        host = host.lower()
        if "://" in host:
            host = host.split("://", 1)[1]
        host = re.sub(r"\s+", "", host.rstrip("/"))
        if not host or host in seen:
            continue
        seen.add(host)
        full = host if host.endswith(".desa.id") else host + ".desa.id"
        key = host[: -len(".desa.id")] if host.endswith(".desa.id") else host
        targets.append(
            {
                "name": NAME_OVERRIDES.get(key, _derive_name(host)),
                "url": "https://" + full,
                "category": "DESA",
                "kecamatan": KECAMATAN_BY_HOST.get(key, ""),
            }
        )
    return targets


TARGETS = _build()
