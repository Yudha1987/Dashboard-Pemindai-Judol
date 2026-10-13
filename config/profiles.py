# -*- coding: utf-8 -*-
"""
Profil pemantauan. Setiap profil berdiri sendiri & independen:
- Target list masing-masing (data.targets / data.targets_opd)
- Port dashboard sendiri (tidak bentrok jika dijalankan bersamaan)
- File output JSON/CSV sendiri (results_*.json / results_*.csv)
- Output directory sendiri (output/desa & output/opd)
- Judul terminal & header dashboard masing-masing
"""

from data import targets as _targets_desa
from data import targets_opd as _targets_opd

PROFILES = {
    "opd": {
        "key": "opd",
        "targets": _targets_opd.TARGETS,
        "port": 8000,
        "output_dir": "output/opd",
        "json_name": "results_opd.json",
        "csv_name": "results_opd.csv",
        "html_name": "dashboard.html",
        "subject": "OPD, Kecamatan, Puskesmas & RS Kabupaten Ngawi (ngawikab.go.id)",
        "entity": "OPD / Instansi",
        "col_label": "Nama Instansi",
        "scope": "OPD/INSTANSI PEMKAB NGAWI",
        "count_label": "OPD",
        "filter_mode": "category",
        "default_interval_min": 1440,
    },
    "desa": {
        "key": "desa",
        "targets": _targets_desa.TARGETS,
        "port": 8001,
        "output_dir": "output/desa",
        "json_name": "results_desa.json",
        "csv_name": "results_desa.csv",
        "html_name": "dashboard.html",
        "subject": "Website Desa Pengguna OpenSID Kabupaten Ngawi (.desa.id)",
        "entity": "Desa",
        "col_label": "Nama Desa",
        "scope": "DESA (OpenSID)",
        "count_label": "desa",
        "filter_mode": "kecamatan",
        "default_interval_min": 1440,
    },
}


def get_profile(profile=None):
    """Return dict profil. Terima kunci string ('opd'/'desa') atau dict."""
    if isinstance(profile, dict):
        return profile
    key = profile if profile in PROFILES else "desa"
    return PROFILES[key]
