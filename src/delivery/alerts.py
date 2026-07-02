"""Alert via Telegram Bot API (Lapisan 7).

Graceful: tanpa TELEGRAM_BOT_TOKEN/CHAT_ID -> cetak ke stdout & return False
(pipeline tidak pernah gagal karena alert). Bahasa netral & probabilistik
(docs/07_compliance.md) — tidak ada perintah "BELI".
"""
from __future__ import annotations

import requests

from config import settings

API = "https://api.telegram.org/bot{token}/sendMessage"


def send(message: str) -> bool:
    """Kirim pesan (Markdown) ke TELEGRAM_CHAT_ID. False bila tak terkonfigurasi/gagal."""
    token, chat = settings.TELEGRAM_BOT_TOKEN, settings.TELEGRAM_CHAT_ID
    if not token or not chat:
        print("[alerts] Telegram tak terkonfigurasi — pesan hanya dicetak:\n" + message)
        return False
    try:
        r = requests.post(
            API.format(token=token),
            json={"chat_id": chat, "text": message, "parse_mode": "Markdown",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        ok = r.status_code == 200 and r.json().get("ok", False)
        if not ok:
            print(f"[alerts] Telegram gagal: HTTP {r.status_code} {r.text[:150]}")
        return ok
    except Exception as exc:  # noqa: BLE001
        print(f"[alerts] Telegram error: {exc}")
        return False
