"""Daftar saham yang dipantau (universe).

US: konstituen S&P 500 dari config/sp500.csv (di-commit -> backtest reproducible).
Bila file hilang, fallback ke 15 mega-cap. IDX ditambahkan di Fase 3.

Universe eksplisit & ter-commit penting: hasil backtest hanya valid jika universe-nya
tetap. Perubahan universe = re-backtest.
"""
from __future__ import annotations

import csv
from pathlib import Path

_SP500_FILE = Path(__file__).parent / "sp500.csv"

# Fallback bila sp500.csv tidak ada (mis. fresh checkout sebelum fetch).
_FALLBACK_US: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "WMT", "XOM", "UNH", "JNJ", "PG", "HD",
]


def _load_sp500() -> list[str]:
    if not _SP500_FILE.exists():
        return []
    with open(_SP500_FILE) as f:
        return [r["symbol"].strip().upper() for r in csv.DictReader(f) if r.get("symbol")]


US_UNIVERSE: list[str] = _load_sp500() or _FALLBACK_US

# --- IDX: ditambahkan di Fase 3 (suffix .JK untuk yfinance) ---
IDX_UNIVERSE: list[str] = []


def all_symbols() -> list[str]:
    """Gabungan universe aktif. IDX kosong sampai Fase 3."""
    return US_UNIVERSE + IDX_UNIVERSE


def market_of(symbol: str) -> str:
    """Kembalikan 'IDX' jika simbol berakhiran .JK, selain itu 'US'."""
    return "IDX" if symbol.upper().endswith(".JK") else "US"
