"""Ingestion harga EOD (US & IDX).

Sumber (pribadi/free): yfinance, Stooq. Untuk versi komersial, GANTI HANYA fungsi di
file ini ke sumber berlisensi (Polygon/Tiingo) — engine di atas tidak berubah.

Tanggung jawab:
  - tarik OHLCV
  - validasi kualitas (tolak harga <= 0, deteksi gap, tangani split/dividen)
  - set kolom `available_at` jujur (EOD tersedia setelah pasar tutup)
  - UPSERT ke tabel `prices` (idempotent)
"""
from __future__ import annotations

from datetime import date


def fetch(symbols: list[str], start: date | None = None, end: date | None = None):
    """Tarik OHLCV untuk daftar simbol, validasi, kembalikan DataFrame siap-UPSERT.

    TODO(impl, Fase 0):
      1. yf.download(...) per batch (hormati REQUEST_DELAY_SEC).
      2. Normalisasi kolom -> skema `prices`.
      3. validate(): drop harga<=0, log gap tanggal.
      4. set market via config.universe.market_of(symbol).
    """
    raise NotImplementedError("Implementasi di Fase 0.")


def validate(df):
    """Cek kualitas: harga > 0, volume >= 0, tanggal monotonik. Kembalikan df bersih + report."""
    raise NotImplementedError
