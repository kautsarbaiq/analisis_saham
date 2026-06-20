"""Daftar saham yang dipantau (universe).

Mulai kecil & terukur: jangan pantau 8000 saham di hari pertama (rate-limit + noise).
Fase 1 fokus ke universe US yang likuid; Fase 3 menambah universe IDX.

Universe sengaja dibuat eksplisit (bukan auto-discover) agar backtest reproducible:
hasil backtest hanya valid jika universe-nya tetap. Perubahan universe = re-backtest.
"""
from __future__ import annotations

# --- US: mulai dari mega/large-cap likuid (data paling bersih) ---
# Placeholder kecil untuk Fase 1. Akan diperluas ke S&P 500 setelah pipeline stabil.
US_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "WMT", "XOM", "UNH", "JNJ", "PG", "HD",
]

# --- IDX: ditambahkan di Fase 3 (suffix .JK untuk yfinance) ---
# Mulai dari LQ45 likuid agar bandarmology proxy punya volume cukup.
IDX_UNIVERSE: list[str] = [
    # "BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK",
    # "BBNI.JK", "UNVR.JK", "ICBP.JK", "GOTO.JK", "ANTM.JK",
]


def all_symbols() -> list[str]:
    """Gabungan universe aktif. IDX kosong sampai Fase 3."""
    return US_UNIVERSE + IDX_UNIVERSE


def market_of(symbol: str) -> str:
    """Kembalikan 'IDX' jika simbol berakhiran .JK, selain itu 'US'."""
    return "IDX" if symbol.upper().endswith(".JK") else "US"
