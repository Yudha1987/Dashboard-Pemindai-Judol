# -*- coding: utf-8 -*-
"""
Modul Integrasi Telegram Bot - Instant Alert untuk website Desa OpenSID.

Fitur:
- Konfigurasi via environment variable atau file .env:
      TELEGRAM_BOT_TOKEN="BOT_TOKEN_ANDA"
      TELEGRAM_CHAT_ID="CHAT_ID_ANDA"
- Mengirim notifikasi SECARA ASYNCHRONOUS (background thread) segera saat
  satu website desa terdeteksi mengandung sisipan judi online / spam,
  tanpa menunggu seluruh daftar selesai dipindai.
- Format pesan mengikuti spesifikasi:
      [PERINGATAN SISIPAN JUDI ONLINE / SPAM DESA (OpenSID)]
- Kegagalan koneksi / token salah hanya dicatat ke log dan TIDAK menghentikan
  pemindaian website lain.
"""

import os
import re
import threading
from datetime import datetime

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
LOG_PATH = os.path.join(PROJECT_ROOT, "logs", "telegram_alert.log")
API_URL = "https://api.telegram.org/bot%s/sendMessage"

_ENV_LOADED = False
BOT_TOKEN = None
CHAT_ID = None

BULAN_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# Karakter khusus Markdown (legacy) yang harus di-escape di dalam nilai.
_MD_SPECIAL = r"_*`["


def _load_env():
    global _ENV_LOADED, BOT_TOKEN, CHAT_ID
    if _ENV_LOADED:
        return
    _ENV_LOADED = True

    token = None
    chat_id = None
    if os.path.isfile(ENV_PATH):
        try:
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key == "TELEGRAM_BOT_TOKEN":
                        token = val
                    elif key == "TELEGRAM_CHAT_ID":
                        chat_id = val
        except OSError:
            pass

    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", token)
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", chat_id)


def _md_escape(text):
    """Escape karakter khusus Markdown di dalam nilai (bukan penanda bold)."""
    s = str(text)
    for ch in _MD_SPECIAL:
        s = s.replace(ch, "\\" + ch)
    return s


def _fmt_tanggal(value):
    """Format tanggal menjadi 'DD Bulan YYYY' (mis. 04 Agustus 2026)."""
    if not value:
        return "-"
    if isinstance(value, datetime):
        try:
            return "%02d %s %d" % (value.day, BULAN_ID[value.month], value.year)
        except IndexError:
            return value.strftime("%d/%m/%Y")
    return str(value)


def _format_alert(data, scope="", entity=""):
    """Susun pesan Markdown sesuai spesifikasi format notifikasi."""
    name = data.get("name") or "-"
    url = data.get("url") or "-"
    last = data.get("last_post") or {}
    judul = last.get("title") or "-"
    tanggal = _fmt_tanggal(last.get("date"))

    scope = scope or "DESA (OpenSID)"
    entity = entity or "Desa"

    keywords = data.get("keywords") or []
    foreign = data.get("foreign_scripts") or []
    critical = bool(data.get("critical")) or bool(foreign)

    kw_text = []
    for k in keywords:
        item = k.get("keyword")
        if item and item not in kw_text:
            kw_text.append(str(item))
    if not kw_text and foreign:
        for f in foreign:
            kw_text.append("%s (%s)" % (f.get("label"), f.get("source")))
    detected = ", ".join(kw_text) if kw_text else "-"
    repeated = data.get("repeated_posts") or []
    if repeated:
        rep_txt = "; ".join('"%s" x%d' % (d.get("title", "")[:60], d.get("count", 0))
                            for d in repeated[:3])
        if len(repeated) > 3:
            rep_txt += " (+%d judul lain)" % (len(repeated) - 3)

    lines = [
        "\U0001F6A8 *PERINGATAN SISIPAN JUDI ONLINE / SPAM %s* \U0001F6A8" % scope,
        "------------------------------------",
        "\U0001F3E1 *Nama %s:* %s" % (entity, _md_escape(name)),
        "\U0001F310 *URL Website:* %s" % _md_escape(url),
        "\U0001F4DD *Judul Postingan Terakhir:* %s" % _md_escape(judul),
        "\U0001F4C5 *Tanggal Postingan:* %s" % _md_escape(tanggal),
        "\u26A0\uFE0F *Terdeteksi:* %s" % _md_escape(detected),
    ]
    if repeated:
        lines.append("\U0001F4DA *Postingan Berulang (%d judul):* %s"
                     % (len(repeated), _md_escape(rep_txt)))
    lines += [
        "------------------------------------",
        "\u26A1 Mohon Admin Kominfo / Operator %s segera melakukan tindakan "
        "takedown/pembersihan!" % entity,
    ]
    if critical:
        lines.append("\n(CRITICAL: terindikasi spam injection / hack bahasa asing)")
    if repeated and not critical:
        lines.append("(Berulang: banyak postingan dengan judul sama "
                     "\u2014 indikasi spam masif)")
    return "\n".join(lines)


def _log(msg):
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), msg))
    except OSError:
        pass


def _send_sync(payload):
    if not BOT_TOKEN or not CHAT_ID:
        return False
    try:
        resp = requests.post(
            API_URL % BOT_TOKEN,
            data={
                "chat_id": CHAT_ID,
                "text": payload,
                "parse_mode": "Markdown",
                "disable_web_page_preview": "true",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            _log("[!] Telegram API error %d: %s" % (resp.status_code, resp.text[:300]))
            return False
        return True
    except requests.RequestException as e:
        _log("[!] Telegram: koneksi gagal - %s: %s" % (e.__class__.__name__, e))
        return False
    except Exception as e:  # noqa: BLE001
        _log("[!] Telegram: error tidak terduga - %s" % e)
        return False


def _worker(data, scope="", entity=""):
    try:
        _send_sync(_format_alert(data, scope=scope, entity=entity))
    except Exception as e:  # noqa: BLE001
        _log("[!] Telegram: gagal menyusun/mengirim alert - %s" % e)


def send_telegram_alert(data, scope="", entity=""):
    """Kirim notifikasi ancaman secara ASYNC (tidak memblokir pemindaian).

    Args:
        data (dict): hasil scan satu website ber-status DETECTED
            (name, url, last_post, keywords, ...).
        scope (str): cakupan pesan, mis. 'DESA (OpenSID)' atau
            'OPD/INSTANSI PEMKAB NGAWI'.
        entity (str): jenis entitas, mis. 'Desa' atau 'OPD / Instansi'.

    Returns:
        bool: True jika alert dijadwalkan ke background thread, False jika
              kredensial belum dikonfigurasi.
    """
    _load_env()
    if not BOT_TOKEN or not CHAT_ID:
        return False
    threading.Thread(target=_worker, args=(data, scope, entity), daemon=True).start()
    return True


# Alias sesuai nama fungsi pada permintaan (sendTelegramAlert(data))
sendTelegramAlert = send_telegram_alert
