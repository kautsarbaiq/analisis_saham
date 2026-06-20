"""Fundamental Engine (Lapisan 5a) — analisis "ala huge fund".

Gabungkan fitur fundamental -> EngineScore 0..100. Skor mentah TIDAK dipercaya sampai
quantile-backtest membuktikan ia memisahkan kinerja masa depan (lihat 05_backtesting.md).
"""
from __future__ import annotations

from datetime import date

from src.types import EngineScore


def score(symbol: str, asof: date) -> EngineScore:
    """Hitung skor fundamental + breakdown terukur.

    TODO(impl, Fase 1):
      - baca fitur fundamental (valuasi/kualitas/kesehatan/growth) dari `features`.
      - normalisasi vs sektor (z-score / percentile).
      - bobotkan jadi 0..100; isi components{} sebagai audit trail.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
