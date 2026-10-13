# -*- coding: utf-8 -*-
"""
Generator Dashboard Penilaian Lomba Website Desa OpenSID 2026.

Menghitung TOTAL SKOR otomatis dari bobot maksimal + data crawler (auto)
+ skor manual juri (nilai_juri.json).

Komponen & bobot:
  1. PROFIL DESA (25%)               [JURI MANUAL]
       - Sejarah Desa & Visi Misi        5
       - SOTK - Struktur Organisasi      5
       - SOTK - Lembaga Desa             5
       - TUPOKSI - Peta Desa             5
       - TUPOKSI - Sinergi Program       5
  2. LAYANAN ADMINISTRASI (35%)      [AUTO - berbasis surat 2026]
  3. UPDATE BERITA / KEGIATAN (20%)
       - Kuantitas Berita              10  [AUTO - artikel 30 hari]
       - Kualitas Berita               10  [JURI MANUAL]
  4. PUBLIKASI REALISASI APBDES (20%)
       - APBDes 2025                   10  [AUTO - widget/menu APBDes 2025]
       - APBDes 2026                   10  [AUTO - widget/menu APBDes 2026]
  ------------------------------------------------------------
  TOTAL                            100
"""

import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

LOGO_LOMBA = "/logo_ngawi.png"

# --- Definisi parameter penilaian ---
PARAMS = {
    "profil_sejarah":      {"label": "Sejarah Desa & Visi Misi", "group": "Profil Desa", "max": 5, "mode": "juri"},
    "profil_sotk_struktur": {"label": "SOTK - Struktur Organisasi", "group": "Profil Desa", "max": 5, "mode": "juri"},
    "profil_sotk_lembaga":  {"label": "SOTK - Lembaga Desa", "group": "Profil Desa", "max": 5, "mode": "juri"},
    "profil_tupoksi_peta":  {"label": "TUPOKSI - Peta Desa", "group": "Profil Desa", "max": 5, "mode": "juri"},
    "profil_tupoksi_sinergi": {"label": "TUPOKSI - Sinergi Program", "group": "Profil Desa", "max": 5, "mode": "juri"},
    "layanan_admin":       {"label": "Layanan Administrasi", "group": "Layanan Administrasi (35%)", "max": 35, "mode": "auto"},
    "kuantitas_berita":    {"label": "Kuantitas Berita", "group": "Update Berita (20%)", "max": 10, "mode": "auto"},
    "kualitas_berita":     {"label": "Kualitas Berita", "group": "Update Berita (20%)", "max": 10, "mode": "juri"},
    "apbdes_2025":         {"label": "APBDes 2025", "group": "Publikasi APBDes (20%)", "max": 10, "mode": "auto"},
    "apbdes_2026":         {"label": "APBDes 2026", "group": "Publikasi APBDes (20%)", "max": 10, "mode": "auto"},
}

# Urutan tampilan grup
GROUPS = [
    ("Profil Desa (25%)", ["profil_sejarah", "profil_sotk_struktur", "profil_sotk_lembaga", "profil_tupoksi_peta", "profil_tupoksi_sinergi"]),
    ("Layanan Administrasi (35%)", ["layanan_admin"]),
    ("Update Berita (20%)", ["kuantitas_berita", "kualitas_berita"]),
    ("Publikasi APBDes (20%)", ["apbdes_2025", "apbdes_2026"]),
]

JURI_PARAMS = [k for k, v in PARAMS.items() if v["mode"] == "juri"]

# --- Baca sumber data ---
def read_json(path, default=None):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


peserta = read_json(os.path.join("output", "lomba", "peserta.json"), [])
if isinstance(peserta, dict):
    peserta = peserta.get("peserta", [])
auto = read_json(os.path.join("output", "lomba", "auto_check.json"))
nilai = read_json(os.path.join("output", "lomba", "nilai_juri.json"))
chk = read_json(os.path.join("output", "lomba", "check_profil.json"))


def _load_monthly_surat():
    """Kembalikan {desa_peserta: {YYYY-MM: n}} utk SEMUA bulan/tahun.

    Skor penilaian tetap memakai bulan 2026 (surat_2026), namun riwayat
    2022-2025 ikut di-embed agar modal rincian surat bisa melihat semua tahun.
    """
    monthly = {}
    try:
        from src.reporter import _load_surat_data
        _, mm, _ = _load_surat_data()
    except Exception:
        mm = {}
    # map URL hasil snapshot -> nama -> monthly
    try:
        rd = read_json(os.path.join("output", "desa", "results_desa.json"))
        rd_by_url = {r["url"].rstrip("/").lower(): r for r in rd.get("results", [])}
    except Exception:
        rd_by_url = {}
    for p in peserta:
        desa = p["desa"]
        key = p["url"].rstrip("/").lower()
        snap = rd_by_url.get(key)
        name = snap.get("name") if snap else None
        mo = {}
        if name and name in mm:
            mo = {k: v for k, v in mm[name].items()}
        monthly[desa] = mo
    return monthly


monthly_surat = _load_monthly_surat()


def _clamp(v, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


# ---- Skor otomatis dari data crawler/checker ----
LAYANAN_SURAT_TARGET = 500  # surat cetak Jan-Agu 2026 utk meraih 35% penuh

def auto_score(p, rec, chkrec):
    out = {}
    # Layanan admin: surat 2026 ke target absolut 500 (diutamakan, 35%)
    surat = rec.get("surat_2026", 0) or 0
    lay = min(surat / LAYANAN_SURAT_TARGET * 35.0, 35.0) if LAYANAN_SURAT_TARGET else 0.0
    out["layanan_admin"] = round(lay, 2)

    # Kuantitas berita (Jan-Agu 2026) proposional, dari checker
    all_art = [c.get("kuantitas_2026", 0) for c in chk.values() if isinstance(c, dict)]
    max_art = max(all_art) if all_art else 0
    art = chkrec.get("kuantitas_2026", 0) if chkrec else 0
    out["kuantitas_berita"] = round(art / max_art * 10, 2) if max_art else 0.0

    # APBDes (realisasi 2025 & 2026) teliti dari checker
    out["apbdes_2025"] = 10.0 if (chkrec and chkrec.get("apbdes_2025")) else 0.0
    out["apbdes_2026"] = 10.0 if (chkrec and chkrec.get("apbdes_2026")) else 0.0
    return out


# Skor komponen Profil & Kualitas Berita dari detection otomatis (ada/tidak)
def desk_check_score(chkrec):
    score = {}
    if not chkrec:
        for k in JURI_PARAMS:
            score[k] = 0.0
        return score
    bool_map = {
        "profil_sejarah": "sejarah_dan_visimisi",
        "profil_sotk_struktur": "sotk_struktur",
        "profil_sotk_lembaga": "sotk_lembaga",
        "profil_tupoksi_peta": "tupoksi_peta",
        "profil_tupoksi_sinergi": "tupoksi_sinergi",
    }
    for k, field in bool_map.items():
        score[k] = float(PARAMS[k]["max"]) if chkrec.get(field) else 0.0
    # kualitas berita 5W+1H (0-10)
    score["kualitas_berita"] = _clamp(chkrec.get("kualitas_berita"), 0, 10)
    return score


def manual_score(desa):
    val = nilai.get(desa, {}) if isinstance(nilai, dict) else {}
    norm = {}
    for k in JURI_PARAMS:
        norm[k] = _clamp(val.get(k, 0.0), 0, float(PARAMS[k]["max"]))
    return norm


# ---- Bangun baris data utk semua peserta ----
rows = []
for p in peserta:
    desa = p["desa"]
    url = p["url"]
    key = url.rstrip("/").lower()
    rec = auto.get(key, {})
    chkrec = chk.get(desa) if isinstance(chk, dict) else None

    autos = auto_score(p, rec, chkrec)
    desks = desk_check_score(chkrec)
    man = manual_score(desa)

    # Isi nilai juri otomatis dari deteksi, tapi tetap bisa dioverride manual.
    # Prioritas: nilai manual eksplisit bila ada di nilai_juri.json,
    #           selain itu pakai hasil deteksi otomatis.
    components = {}
    total = 0.0
    for k, v in list(autos.items()):
        components[k] = v
        total += v
    for k in JURI_PARAMS:
        auto_v = desks.get(k, 0.0)
        if k in man and (man[k] != 0.0 or auto_v == 0.0):
            v = man[k]
        else:
            v = auto_v
        components[k] = float(v)
        total += v
    total = round(total, 2)

    rows.append({
        "no": p["no"],
        "desa": desa,
        "kecamatan": p["kecamatan"],
        "url": url,
        "http_ok": rec.get("http_ok", False),
        "http_status": rec.get("http_status"),
        "apbdes_2025": bool(chkrec.get("apbdes_2025")) if chkrec else rec.get("apbdes_2025", False),
        "apbdes_2026": bool(chkrec.get("apbdes_2026")) if chkrec else rec.get("apbdes_2026", False),
        "apbdes_lokasi": (chkrec.get("apbdes_lokasi", {}) if chkrec else
                          {"2025": [], "2026": []}),
        "surat_2026": rec.get("surat_2026", 0),
        "kuantitas_2026": chkrec.get("kuantitas_2026", 0) if chkrec else 0,
        "konten_default": (chkrec.get("konten_default", []) if chkrec else []),
        "monthly": monthly_surat.get(desa, {}),
        "components": components,
        "total": total,
        "juri_done": all(man.get(k, 0) >= 0 for k in JURI_PARAMS),
    })

# Ranking urut Total Skor dari terbesar ke terkecil
rows.sort(key=lambda r: r["total"], reverse=True)

# Statistik ringkas
count_complete_auto = sum(1 for r in rows if r["total"] > 0)
max_total = max((r["total"] for r in rows), default=0)

# ---- Serialisasi data utk JS ----
def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

# --- Urutan kolom komponen (dari Sejarah s/d APBDes 2026) ---
COMPONENT_ORDER = [
    ("profil_sejarah", "Sejarah&VM", "Sejarah Desa & Visi Misi (5%)"),
    ("profil_sotk_struktur", "SOTK", "SOTK - Struktur Organisasi (5%)"),
    ("profil_sotk_lembaga", "Lembaga", "SOTK - Lembaga Desa (5%)"),
    ("profil_tupoksi_peta", "Peta", "TUPOKSI - Peta Desa (5%)"),
    ("profil_tupoksi_sinergi", "Sinergi", "TUPOKSI - Sinergi Program (5%)"),
    ("layanan_admin", "Layanan", "Layanan Administrasi (35%)"),
    ("kuantitas_berita", "Kuant.", "Kuantitas Berita (10%)"),
    ("kualitas_berita", "Kualitas", "Kualitas Berita (10%)"),
    ("apbdes_2025", "APB 2025", "Publikasi Realisasi APBDes 2025 (10%)"),
    ("apbdes_2026", "APB 2026", "Publikasi Realisasi APBDes 2026 (10%)"),
]
COMPONENT_KEYS = [k for k, _, _ in COMPONENT_ORDER]
comp_th = "".join(
    f'<th style="text-align:center" title="{t}">{l}<br><span style="font-weight:400;font-size:10px;color:#94a3b8">%</span></th>'
    for _, l, t in COMPONENT_ORDER)
comp_export_names = ["Nilai_" + PARAMS[k]["label"].replace(" ", "_") for k in COMPONENT_KEYS]

rows_json = compact(rows)
params_json = compact(PARAMS)
groups_json = compact(GROUPS)
juri_params_json = compact(JURI_PARAMS)
comp_keys_json = compact(COMPONENT_KEYS)

# Waktu update cobek (dari salah satu record auto)
_ca = next((v.get("checked_at") for v in auto.values()), None)
checked_at_line = f'Update: {_ca}' if _ca else 'Update: -'

html = f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" type="image/png" href="{LOGO_LOMBA}">
<title>Penilaian Lomba Website Desa 2026 - Kabupaten Ngawi</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Tahoma,sans-serif;background:#f1f5f9;color:#1e293b;line-height:1.4}}
.header{{background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 100%);background-image:url("/assets/bg-header.svg");background-size:cover;background-position:center;padding:24px 32px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}}
.header-left{{display:flex;align-items:center;gap:16px}}
.header-logos{{display:flex;align-items:center;gap:14px}}
.header-logos img{{height:56px;width:auto;filter:drop-shadow(0 2px 4px rgba(0,0,0,.2))}}
.header h1{{font-size:24px;font-weight:800;color:#000}}
.header .subtitle{{font-size:13px;color:#222;margin-top:2px}}
.header .badge{{background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.25);border-radius:8px;padding:8px 14px;font-size:13px;line-height:1.6;color:#fff}}
.container{{max-width:1400px;margin:0 auto;padding:20px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:22px}}
.stat-box{{background:#fff;border-radius:12px;padding:18px 16px;box-shadow:0 2px 8px rgba(0,0,0,.06);border-left:4px solid #2563eb;text-align:center}}
.stat-box.green{{border-left-color:#16a34a}}.stat-box.amber{{border-left-color:#f59e0b}}.stat-box.red{{border-left-color:#ef4444}}
.stat-box .num{{font-size:30px;font-weight:800;color:#1e3a5f}}
.stat-box .lbl{{font-size:11px;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.card{{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.06);overflow:hidden;margin-bottom:22px}}
.card-title{{padding:14px 18px;font-size:15px;font-weight:700;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}
.card-title span{{color:#64748b;font-weight:400;font-size:12px}}
.toolbar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.toolbar input,.toolbar select{{padding:6px 10px;border:1px solid #d1d5db;border-radius:8px;font-size:13px;outline:none}}
.toolbar input{{width:200px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#f8fafc;font-weight:600;text-align:left;padding:9px 10px;border-bottom:2px solid #e2e8f0;color:#475569;position:sticky;top:0;z-index:2;white-space:nowrap}}
td{{padding:8px 10px;border-bottom:1px solid #f1f5f9}}
tr.data-row:hover td{{background:#f0f7ff}}
.table-wrap{{max-height:640px;overflow-y:auto}}
.rank-badge{{display:inline-flex;width:28px;height:28px;border-radius:50%;align-items:center;justify-content:center;font-weight:700;font-size:12px}}
.r1{{background:linear-gradient(135deg,#FEF08A,#FDE047);color:#854D0E}}
.r2{{background:linear-gradient(135deg,#E2E8F0,#CBD5E1);color:#334155}}
.r3{{background:linear-gradient(135deg,#FFEDD5,#FED7AA);color:#9A3412}}
.rn{{background:#e2e8f0;color:#64748b}}
.total-cell{{font-weight:800;font-size:15px;color:#1e3a5f}}
.tag{{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:10px;white-space:nowrap}}
.ok{{background:#DCFCE7;color:#166534}}
.no{{background:#FEE2E2;color:#991B1B}}
.mut{{background:#E0E7FF;color:#3730A3}}
.btn{{background:#2563eb;color:#fff;border:none;border-radius:6px;padding:5px 10px;font-size:11px;cursor:pointer;text-decoration:none;display:inline-block}}
.btn:hover{{background:#1d4ed8}}
.btn-green{{background:#16a34a}}.btn-green:hover{{background:#15803d}}
.btn-outline{{background:#fff;color:#2563eb;border:1px solid #2563eb}}
.bar-w{{width:120px;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;display:inline-block;vertical-align:middle}}
.bar-f{{height:100%;background:linear-gradient(90deg,#2563eb,#0ea5e9)}}
.footer{{text-align:center;padding:20px;color:#94a3b8;font-size:11px}}
.modal-overlay{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.5);z-index:1000;justify-content:center;align-items:center;backdrop-filter:blur(2px)}}
.modal-overlay.show{{display:flex}}
.modal-box{{background:#fff;border-radius:16px;max-width:680px;width:94%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,.25)}}
.modal-header{{padding:18px 22px 12px;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:flex-start;position:sticky;top:0;background:#fff;z-index:3}}
.modal-header h2{{font-size:18px;font-weight:700;color:#1e3a5f}}
.modal-header .sub{{font-size:12px;color:#64748b;margin-top:2px}}
.modal-close{{background:none;border:none;font-size:24px;cursor:pointer;color:#94a3b8}}
.modal-body{{padding:16px 22px 22px}}
.form-group{{margin-bottom:8px;padding:10px 12px;border:1px solid #f1f5f9;border-radius:10px;background:#f8fafc}}
.form-group .glabel{{font-size:12px;font-weight:700;color:#475569;margin:10px 0 4px}}
.form-row{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:5px 0;border-bottom:1px dashed #e2e8f0}}
.form-row:last-child{{border-bottom:none}}
.form-row label{{font-size:13px;color:#1e293b;flex:1}}
.form-row .mmax{{font-size:11px;color:#94a3b8}}
.form-row input[type=number]{{width:80px;padding:6px 8px;border:1px solid #d1d5db;border-radius:8px;font-size:14px;text-align:center}}
.auto-row{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:5px 0;border-bottom:1px dashed #e2e8f0;color:#64748b}}
.auto-row:last-child{{border-bottom:none}}
.lokasi-box{{margin-top:4px;padding:4px 8px;font-size:11px;color:#475569;background:#f8fafc;border-radius:4px}}
.lokasi-item{{margin:2px 0;color:#64748b}}
.lokasi-box.muted{{color:#94a3b8;font-style:italic}}
.default-warn{{margin:0 0 6px;padding:8px 10px;font-size:12px;line-height:1.45;color:#7c2d12;background:#fff7ed;border:1px solid #fed7aa;border-radius:8px}}
.default-warn strong{{display:block;margin-bottom:2px;color:#c2410c}}
.modal-sum{{display:flex;gap:12px;margin-top:14px;padding:12px;background:#eef2ff;border-radius:10px}}
.modal-sum .s{{flex:1;text-align:center}}
.modal-sum .sv{{font-size:22px;font-weight:800;color:#1e3a5f}}
.modal-sum .sl{{font-size:11px;color:#475569;text-transform:uppercase}}
.modal-actions{{display:flex;gap:10px;margin-top:14px;justify-content:flex-end}}
.toolbar-hint{{font-size:11px;color:#64748b;margin-top:6px}}
.link-btn{{background:#2563eb;color:#fff;border:none;border-radius:6px;padding:5px 10px;font-size:11px;cursor:pointer;text-decoration:none;display:inline-block}}
.desa-link{{color:#1e3a5f;text-decoration:none;cursor:pointer}}
.desa-link:hover{{color:#2563eb;text-decoration:underline}}
</style>
</head>
<body>
<div class="header">
  <div class="header-left">
    <div class="header-logos">
      <img src="/logo_ngawi.png" alt="Pemkab Ngawi">
      <img src="/logo.png" alt="Diskominfo">
    </div>
    <div>
      <h1>Penilaian Lomba Website Desa 2026</h1>
      <div class="subtitle">Kabupaten Ngawi &mdash; Total Skor Otomatis dari Bobot &amp; Penilaian Juri</div>
    </div>
  </div>
  <div class="badge">{len(rows)} Peserta<br>{checked_at_line}</div>
</div>

<div class="container">
  <div class="stats">
    <div class="stat-box"><div class="num">{len(rows)}</div><div class="lbl">Total Peserta</div></div>
    <div class="stat-box green"><div class="num" id="statComplete"></div><div class="lbl">Terverifikasi Auto</div></div>
    <div class="stat-box amber"><div class="num" id="statAvg"></div><div class="lbl">Rata-rata Skor</div></div>
    <div class="stat-box red"><div class="num">{max_total}</div><div class="lbl">Skor Tertinggi</div></div>
  </div>

  <div class="card">
    <div class="card-title">
      Data Penilaian &amp; Skor Final
      <div class="toolbar">
        <select id="kecSelect" onchange="filterTable()"><option value="">Semua Kecamatan</option>{''.join(f'<option>{k}</option>' for k in sorted({r['kecamatan'] for r in rows}))}</select>
        <input id="searchInput" placeholder="Cari desa..." oninput="filterTable()">
        <button class="btn btn-outline" onclick="resetFilters()">Reset</button>
        <button class="btn btn-green" onclick="exportCSV()">Export CSV</button>
      </div>
      <div class="toolbar-hint">Urutan baris berdasar Total Skor (terbesar → terkecil). Klik "Nilai Juri" untuk mengisi/mengedit skor manual juri. Skor otomatis (Layanan Admin, Kuantitas Berita, APBDes) dihitung dari crawler &amp; data surat.</div>
    </div>
    <div class="table-wrap">
      <table id="mainTable">
        <thead>
          <tr>
            <th style="width:34px">#</th>
            <th>Desa</th>
            <th>Kecamatan</th>
            {comp_th}
            <th style="text-align:right">Total Skor</th>
            <th style="width:110px">Kemajuan</th>
            <th style="width:170px;">Aksi</th>
          </tr>
        </thead>
        <tbody id="tableBody"></tbody>
      </table>
    </div>
  </div>
</div>

<div class="footer">
  Bobot: Profil Desa 25% &bull; Layanan Administrasi 35% &bull; Update Berita 20% &bull; Publikasi APBDes 20% &mdash; Total 100%
</div>

<!-- Modal Nilai Juri -->
<div class="modal-overlay" id="modalOverlay" onclick="if(event.target===this)closeModal()">
  <div class="modal-box">
    <div class="modal-header">
      <div>
        <h2 id="modalName">Form Nilai Juri</h2>
        <div class="sub" id="modalSub"></div>
      </div>
      <button class="modal-close" onclick="closeModal()">&times;</button>
    </div>
    <div class="modal-body">
      <div id="modalForm"></div>
      <div class="modal-sum">
        <div class="s"><div class="sv" id="modJuriTotal">0</div><div class="sl">Skor Juri</div></div>
        <div class="s"><div class="sv" id="modAutoTotal">0</div><div class="sl">Skor Auto</div></div>
        <div class="s"><div class="sv" id="modGrandTotal">0</div><div class="sl">Total</div></div>
      </div>
      <div class="modal-actions">
        <button class="btn btn-outline" onclick="closeModal()">Tutup</button>
        <button class="btn btn-green" onclick="saveJuri()">Simpan Nilai</button>
      </div>
    </div>
  </div>
</div>

<!-- Modal Surat Tercetak per Bulan -->
<div class="modal-overlay" id="suratModalOverlay" onclick="if(event.target===this)closeSuratModal()">
  <div class="modal-box" style="max-width:420px">
    <div class="modal-header">
      <div>
        <h2 id="suratModalName">Surat Tercetak</h2>
        <div class="sub" id="suratModalTotal"></div>
      </div>
      <button class="modal-close" onclick="closeSuratModal()">&times;</button>
    </div>
    <div class="modal-body">
      <div id="suratModalBody"></div>
      <p style="font-size:11px;color:#94a3b8;margin-top:10px">Jumlah surat tercetak Januari s/d Agustus 2026.</p>
    </div>
  </div>
</div>

<script>
const ROWS = {rows_json};
const PARAMS = {params_json};
const JURI_PARAMS = {juri_params_json};
const COMPONENT_KEYS = {comp_keys_json};

function num(v){{ return typeof v==='number' ? v : (parseFloat(v)||0); }}
function fmt(v){{ return num(v).toFixed(2); }}
let CUR_DESA = null;

function compCell(r, k){{
  const v = num(r.components[k]);
  const m = PARAMS[k].max;
  let cls = '';
  if(v >= m) cls = ' style="color:#166534;font-weight:700"';
  else if(v > 0) cls = ' style="color:#b45309;font-weight:700"';
  else cls = ' style="color:#cbd5e1"';
  return '<td style="text-align:center"' + cls + ' title="'+PARAMS[k].label+'">'+fmt(v)+'%</td>';
}}

function openModal(elOrName){{
  const desa = (typeof elOrName === 'string') ? elOrName : elOrName.closest('tr').getAttribute('data-desa');
  CUR_DESA = desa;
  const r = ROWS.find(x => x.desa === desa);
  if(!r) return;
  document.getElementById('modalName').textContent = r.desa;
  document.getElementById('modalSub').textContent = 'Kecamatan ' + r.kecamatan +
    ' &middot; ' + (r.url.endsWith('/') ? r.url.slice(0, -1) : r.url);
  let html = '';
  // Peringatan konten default OpenSID (Senggigi/Lombok)
  if(r.konten_default && r.konten_default.length){{
    html += '<div class="default-warn"><strong>&#9888; Konten bawaan OpenSID terdeteksi</strong>' +
      '<div>Profil ini masih memakai contoh bawaan &ldquo;Desa Senggigi (Lombok)&rdquo;. ' +
      'Komponen berikut dinilai 0 sampai juri memberi nilai manual: ' +
      r.konten_default.map(k=>PARAMS[k]?PARAMS[k].label:k).join(', ') + '.</div></div>';
  }}
  // Grup manual (juri)
  for (const [gname, keys] of GROUPS){{
    const juriKeys = keys.filter(k => PARAMS[k].mode === 'juri');
    const autoKeys = keys.filter(k => PARAMS[k].mode === 'auto');
    html += '<div class="glabel">' + gname + '</div>';
    if(autoKeys.length){{
      autoKeys.forEach(k => {{
        const sc = r.components[k] || 0;
        html += '<div class="auto-row"><span><strong>'+PARAMS[k].label+'</strong> <span class="mmax">(auto)</span></span><span style="font-weight:600;color:#1e3a5f">'+fmt(sc)+'%</span></div>';
      }});
    }}
    if(juriKeys.length){{
      juriKeys.forEach(k => {{
        html += '<div class="form-row"><label>'+PARAMS[k].label+'<span class="mmax"> (maks '+PARAMS[k].max+')</span></label><input type="number" id="juri_'+k+'" min="0" max="'+PARAMS[k].max+'" step="0.5" value="'+(r.components[k]||0)+'" oninput="liveTotals()"></div>';
      }});
    }}
  }}
  // Log lokasi APBDes 2025 & 2026
  const lokasi = r.apbdes_lokasi || {{'2025':[],'2026':[]}};
  html += '<div class="glabel">Log Lokasi Publikasi APBDes</div>';
  [['2025','APBDes 2025'],['2026','APBDes 2026']].forEach(([yr,lab]) => {{
    const ada = (r.components['apbdes_'+yr]||0) > 0;
    const ls = (lokasi[yr]||[]).slice();
    if(ls.length && !ls.some(s => s.indexOf('Galeri')>=0)) ls.push('(kemungkinan galeri/gambar)');
    html += '<div class="auto-row"><span><strong>'+lab+'</strong> <span class="mmax">('+(ada?'ADA':'TIDAK ADA')+', nilainya '+(r.components['apbdes_'+yr]||0)+'%)</span></span></div>';
    if(ls.length){{
      html += '<div class="lokasi-box">'+ls.map(s=>'<div class="lokasi-item">'+s+'</div>').join('')+'</div>';
    }} else {{
      html += '<div class="lokasi-box muted">Tidak ditemukan di menu, sidebar, artikel, galeri, maupun widget halaman bawah.</div>';
    }}
  }});
  document.getElementById('modalForm').innerHTML = html;
  document.getElementById('modJuriTotal').textContent = '0%';
  document.getElementById('modAutoTotal').textContent = '0%';
  document.getElementById('modGrandTotal').textContent = fmt(r.total) + '%';
  liveTotals();
  document.getElementById('modalOverlay').classList.add('show');
}}

function liveTotals(){{
  const desa = CUR_DESA;
  const r = ROWS.find(x => x.desa === desa);
  let juriSum = 0;
  JURI_PARAMS.forEach(k => {{
    const el = document.getElementById('juri_'+k);
    if(el){{ const v = Math.max(0, Math.min(PARAMS[k].max, num(el.value))); el.value = v; juriSum += v; }}
  }});
  let autoSum = 0;
  Object.keys(PARAMS).forEach(k => {{ if(PARAMS[k].mode==='auto') autoSum += num(r.components[k]); }});
  document.getElementById('modJuriTotal').textContent = fmt(juriSum) + '%';
  document.getElementById('modAutoTotal').textContent = fmt(autoSum) + '%';
  document.getElementById('modGrandTotal').textContent = fmt(juriSum + autoSum) + '%';
}}

function saveJuri(){{
  const desa = document.getElementById('modalName').textContent;
  const r = ROWS.find(x => x.desa === desa);
  const payload = {{ desa: desa }};
  JURI_PARAMS.forEach(k => {{
    const el = document.getElementById('juri_'+k);
    payload[k] = el ? num(el.value) : 0;
  }});
  fetch('/api/lomba/nilai', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }}).then(res => res.json()).then(res => {{
    alert(res.message || 'Tersimpan');
    location.reload();
  }}).catch(()=>alert('Gagal menyimpan'));
}}

function getRankCls(i){{ return i===0?'r1':(i===1?'r2':(i===2?'r3':'rn')); }}
function getRankIcon(i){{ if(i===0)return '&#127942;'; if(i===1)return '&#129349;'; if(i===2)return '&#129351;'; return (i+1).toString(); }}

function renderTable(data){{
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  data.forEach((r,i) => {{
    const pct = Math.min(100, r.total);
    let cells = '';
    COMPONENT_KEYS.forEach(k => cells += compCell(r,k));
    tbody.innerHTML += '<tr class="data-row" data-desa="'+r.desa+'">' +
      '<td><span class="rank-badge '+getRankCls(i)+'">'+getRankIcon(i)+'</span></td>' +
      '<td><a class="desa-link" href="javascript:void(0)" onclick="showMonthlySurat(this)" title="Klik utk lihat surat per bulan"><strong>'+r.desa+'</strong></a>' +
        '<div style="font-size:10px;color:#94a3b8">surat '+r.surat_2026+'</div></td>' +
      '<td style="color:#64748b;font-size:12px">'+r.kecamatan+'</td>' +
      cells +
      '<td style="text-align:right" class="total-cell">'+fmt(r.total)+'%</td>' +
      '<td><span class="bar-w"><span class="bar-f" style="width:'+pct+'%"></span></span></td>' +
      '<td style="white-space:nowrap">' +
        '<a class="link-btn" href="'+r.url+'" target="_blank">Buka</a> ' +
        '<button class="btn btn-green" onclick="openModal(this)">Nilai</button>' +
      '</td></tr>';
  }});
}}

function showMonthlySurat(elOrName){{
  const desa = (typeof elOrName === 'string') ? elOrName : elOrName.closest('tr').getAttribute('data-desa');
  const r = ROWS.find(x => x.desa === desa);
  if(!r) return;
  document.getElementById('suratModalName').textContent = 'Surat Tercetak - ' + desa;

  // Kumpulkan semua tahun dari data monthly (bukan hanya 2026)
  const mo = r.monthly || {{}};
  const tahunSet = {{}};
  Object.keys(mo).forEach(ym => {{ if(ym.length >= 4) tahunSet[ym.substring(0,4)] = true; }});
  const tahunList = Object.keys(tahunSet).sort().reverse();
  if (tahunList.length === 0) tahunList.push(String(new Date().getFullYear()));

  // Total per tahun utk ditampilkan di header
  const totByYear = {{}};
  Object.keys(mo).forEach(ym => {{
    const y = ym.substring(0,4);
    totByYear[y] = (totByYear[y] || 0) + (mo[ym] || 0);
  }});

  // Selector tahun + tombol: 2026 utk skor lomba, sisanya riwayat
  let selHtml = '<select id="suratYearSel" onchange="renderSuratYear(this.value)">';
  tahunList.forEach(y => {{
    selHtml += '<option value="'+y+'"'+(y==='2026'?' selected':'')+'>'+y+
               ' (Total '+(totByYear[y] || 0)+')</option>';
  }});
  selHtml += '</select>';
  document.getElementById('suratModalTotal').innerHTML =
    '<div style="font-size:12px;color:#64748b;margin-top:4px">'+
    'Total 2026 (penilaian): <b style="color:#1e3a5f">'+(r.surat_2026||0)+' surat</b> · '+
    'Semua tahun: <b>'+(tahunList.map(y=>(y+': '+(totByYear[y]||0))).join(', '))+'</b>'+
    '</div>';
  document.getElementById('suratModalBody').innerHTML =
    '<div style="margin-bottom:10px">'+selHtml+'</div><div id="suratYearGrid"></div>';
  renderSuratYear('2026');
  document.getElementById('suratModalOverlay').classList.add('show');
}}

function renderSuratYear(year){{
  const r = ROWS.find(x => x.desa === document.getElementById('suratModalName').textContent.replace('Surat Tercetak - ',''));
  if(!r) return;
  const mo = r.monthly || {{}};
  let html = '<table style="width:100%;border-collapse:collapse;font-size:13px">' +
    '<tr><th style="text-align:left;padding:6px 8px;background:#f8fafc;border-bottom:2px solid #e2e8f0">Bulan</th>' +
    '<th style="text-align:right;padding:6px 8px;background:#f8fafc;border-bottom:2px solid #e2e8f0">Jumlah Surat</th></tr>';
  let grand = 0;
  const NM = ['Januari','Februari','Maret','April','Mei','Juni','Juli','Agustus','September','Oktober','November','Desember'];
  for(let m=1; m<=12; m++){{
    const key = year + '-' + (m<10?'0'+m:''+m);
    const v = mo[key] || 0;
    grand += v;
    html += '<tr><td style="padding:6px 8px;border-bottom:1px solid #f1f5f9">'+NM[m-1]+' '+year+'</td>' +
            '<td style="padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right;font-weight:700">'+v+'</td></tr>';
  }}
  html += '<tr><td style="padding:6px 8px;font-weight:800">Total '+year+'</td>' +
          '<td style="padding:6px 8px;text-align:right;font-weight:800;color:#1e3a5f">'+grand+'</td></tr>' +
          '</table>';
  document.getElementById('suratYearGrid').innerHTML = html;
}}

function closeModal(){{ document.getElementById('modalOverlay').classList.remove('show'); }}
function closeSuratModal(){{ document.getElementById('suratModalOverlay').classList.remove('show'); }}

function getFiltered(){{
  const q = document.getElementById('searchInput').value.toLowerCase();
  const kec = document.getElementById('kecSelect').value;
  return ROWS.filter(r =>
    (!q || r.desa.toLowerCase().includes(q)) &&
    (!kec || r.kecamatan === kec));
}}
function filterTable(){{ renderTable(getFiltered()); }}
function resetFilters(){{ document.getElementById('searchInput').value=''; document.getElementById('kecSelect').value=''; filterTable(); }}

function exportCSV(){{
  const hdr = ['No','Desa','Kecamatan','URL','Surat2026','KuantitasBerita2026',
               ...COMPONENT_KEYS.map(k=>PARAMS[k].label),'TotalSkor(%)'];
  const rows = [hdr];
  ROWS.forEach(r => {{
    const row = [r.no, r.desa, r.kecamatan, r.url, r.surat_2026, r.kuantitas_2026];
    COMPONENT_KEYS.forEach(k => row.push(r.components[k]));
    row.push(r.total);
    rows.push(row);
  }});
  const csv = rows.map(r => r.map(c => '"'+String(c).replace(/"/g,'""')+'"').join(',')).join('\\n');
  const blob = new Blob(["\ufeff"+csv], {{type:'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'penilaian_lomba_desa_2026.csv';
  a.click();
  URL.revokeObjectURL(a.href);
}}

// init stats
const GROUPS = {groups_json};
document.getElementById('statComplete').textContent = ROWS.filter(r=>r.http_ok).length;
document.getElementById('statAvg').textContent = (ROWS.reduce((a,r)=>a+r.total,0)/ROWS.length).toFixed(1);

renderTable(ROWS);
</script>
</body>
</html>
"""

os.makedirs(os.path.join("output", "lomba"), exist_ok=True)
with open(os.path.join("output", "lomba", "dashboard.html"), "w", encoding="utf-8") as f:
    f.write(html)

# Hitung ringkasan
summary = [{"no": r["no"], "desa": r["desa"], "kecamatan": r["kecamatan"],
            "total": r["total"], "components": r["components"]} for r in rows]
with open(os.path.join("output", "lomba", "skor_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("Dashboard penilaian lomba dibangkitkan: output/lomba/dashboard.html")
print(f"Total 38 peserta, skor tertinggi {max_total}")
