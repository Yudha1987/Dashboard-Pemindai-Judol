# -*- coding: utf-8 -*-
"""
Helper untuk mendapatkan CHAT_ID Telegram.

Cara pakai:
  1. Buat bot lewat @BotFather, salin token-nya.
  2. Kirim pesan apa pun ke bot Anda dari akun Telegram Anda.
  3. Jalankan:
        python tools/get_chat_id.py --token=<BOT_TOKEN>
  4. Masukkan TELEGRAM_CHAT_ID hasilnya ke file .env
"""

import argparse

import requests


def get_updates(token):
    url = "https://api.telegram.org/bot%s/getUpdates" % token
    resp = requests.get(url, timeout=15)
    data = resp.json()
    if not data.get("ok"):
        raise SystemExit("Gagal memanggil getUpdates: %s" % data.get("description"))
    if not data.get("result"):
        raise SystemExit(
            "Belum ada pesan masuk ke bot. Kirim pesan ke bot Anda dulu, "
            "lalu jalankan ulang."
        )
    chat_ids = []
    for update in data["result"]:
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat") or {}
        cid = chat.get("id")
        first = chat.get("first_name") or chat.get("username") or cid
        if cid is not None and cid not in chat_ids:
            chat_ids.append((cid, first))
    return chat_ids


def main():
    parser = argparse.ArgumentParser(description="Ambil CHAT_ID Telegram")
    parser.add_argument("--token", required=True, help="Token bot dari @BotFather")
    args = parser.parse_args()

    for cid, name in get_updates(args.token):
        print("CHAT_ID = %s  (dari: %s)" % (cid, name))
    print("\nMasukkan TELEGRAM_CHAT_ID tersebut ke file .env")


if __name__ == "__main__":
    main()
