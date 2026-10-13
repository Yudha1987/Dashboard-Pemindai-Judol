# -*- coding: utf-8 -*-
"""
Kamus kata kunci deteksi judi online / slot / togel / spam SEO & spam bahasa
asing, sesuai spesifikasi pemantau website Desa OpenSID Kabupaten Ngawi.

Catatan:
- Kata kunci pendek (mis. "slot", "gacor", "zeus") dicocokkan dengan
  word-boundary agar tidak false-positive terhadap kata lain.
- Kata kunci "toto" polos tidak dipakai (false-positive terhadap budaya
  "Toto Suro" & class "scrollToTop"); diganti frasa gambling yang spesifik.
- Kata kunci non-Latin (Thai, Vietnam beraksen, Cyrillic) dicocokkan sebagai
  substring (akasara non-Latin tidak mendukung word-boundary).
- Kategori "Spam Pinjaman / Kredit" & "Spam Bahasa Asing" dianggap serangan
  siber prioritas tinggi dan otomatis menaikkan status menjadi CRITICAL agar
  segera ditindaklanjuti admin Kominfo (lihat CYBER_CATEGORIES di detector.py).
- Hasil deteksi tetap wajib diverifikasi manual oleh Admin sebelum tindakan.
"""

KEYWORDS = {
    # A. Judi Online / Slot / Togel
    "Judi Online / Slot / Togel": [
        "slot", "gacor", "maxwin", "rtp live", "pragmatic", "pg soft",
        "zeus", "gates of olympus", "mahjong ways", "anti rungkad",
        "pasti jp", "depo pulsa", "link alternatif", "situs judi",
        "dramatoto", "kingdomtoto", "togel", "toto 4d", "toto4d",
        "toto macau", "toto88", "bandar toto", "toto online",
        "prediksi toto", "bocoran hk", "live casino", "baccarat",
        "sabung ayam",
    ],
    # B1. Spam Pinjaman / Kredit / Pinjol (Bahasa Indonesia & Inggris)
    # Postingan spam pinjaman ilegal ("Tips Cara Membatalkan Pinjaman" dll).
    # Frasa dipilih yang bermuatan promosi/pemasaran pinjol; hindari kata polos
    # seperti "dana"/"kredit"/"pinjaman" agar tidak false-positive dengan
    # aktivitas resmi (dana desa, kredit usaha, pinjaman BPD).
    "Spam Pinjaman / Kredit": [
        "pinjaman tanpa agunan", "pinjaman tanpa jaminan",
        "pinjaman pakai ktp", "pinjaman bunga rendah", "pinjaman bungan rendah",
        "cair tanpa agunan", "dana cepat cair", "dana cair hari ini",
        "butuh dana cepat",
        "mencairkan pinjaman", "membatalkan pinjaman", "cara membatalkan pinjaman",
        "tip membatalkan pinjaman", "tips membatalkan pinjaman",
        "credit card newbies", "no credit check loans",
        "cash advance", "quick loan", "cash loan", "fast cash loan",
        "instant cash loan", "easy loan",
    ],
    # B2. Spam SEO & Link Injection (Bahasa Inggris)
    "Spam SEO / Link Injection (Inggris)": [
        "online casino", "free spins", "no deposit bonus", "payday loans",
        "cheap viagra",
    ],
    # B3. Spam Bahasa Thai
    "Spam Thai": [
        "สล็อต", "สล็อตเว็บตรง", "คาสิโนออนไลน์", "ฝากถอนไม่มีขั้นต่ำ",
    ],
    # B4. Spam Bahasa Vietnam
    "Spam Vietnam": [
        "nhà cái", "kèo nhà cái",
    ],
    # B5. Spam Bahasa Cyrillic (Rusia)
    "Spam Cyrillic": [
        "казино", "слоты",
    ],
}

# Aksara non-Latin yang mencurigakan sebagai spam injection / hack.
NON_LATIN_SCRIPTS = [
    {
        "id": "thai",
        "label": "Karakter Non-Latin (Thai)",
        "regex": r"[\u0E00-\u0E7F]",
    },
    {
        "id": "cyrillic",
        "label": "Karakter Non-Latin (Cyrillic)",
        "regex": r"[\u0400-\u04FF]",
    },
]
