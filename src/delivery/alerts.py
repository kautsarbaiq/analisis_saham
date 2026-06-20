"""Alert real-time via Telegram (Lapisan 7).

Hanya kirim saat ada event TERUKUR: berita penting + forecast event-study,
breakout tervalidasi, anomali volume, atau akumulasi bandar (proxy).
Bahasa netral & probabilistik (lihat 07_compliance.md) — tidak ada perintah "BELI".
"""
from __future__ import annotations


def send(message: str) -> bool:
    """Kirim pesan ke TELEGRAM_CHAT_ID via Bot API. Kembalikan sukses/gagal.

    TODO(impl, Fase 2): POST api.telegram.org/bot<token>/sendMessage.
    """
    raise NotImplementedError("Implementasi di Fase 2.")


def format_signal(symbol: str, prediction) -> str:
    """Format alert: simbol, tipe event, P naik, CI, N, + disclaimer singkat."""
    raise NotImplementedError
