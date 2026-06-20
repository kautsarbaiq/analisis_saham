"""Technical Engine (Lapisan 5b).

Aturan keras: sebuah pola hanya menyumbang skor untuk saham/sektor tertentu jika
edge-nya TERBUKTI lewat backtest. Tidak ada indikator yang dipercaya hanya karena teori.
"""
from __future__ import annotations

from datetime import date

from src.types import EngineScore


def score(symbol: str, asof: date) -> EngineScore:
    """Hitung skor teknikal dari fitur tervalidasi.

    TODO(impl, Fase 1):
      - baca fitur teknikal dari `features`.
      - untuk tiap sinyal aktif, ambil edge backtest-nya (win-rate, N).
      - sinyal belum tervalidasi -> bobot 0 (tetap ditampilkan sebagai info).
    """
    raise NotImplementedError("Implementasi di Fase 1.")
