"""Sentiment Engine (Lapisan 5c, bagian kontinu).

Agregasi skor sentimen berita terbaru per saham -> komponen skor harian.
Event-study terpisah ada di event_study.py (fitur prediksi unggulan).
"""
from __future__ import annotations

from datetime import date

from src.types import EngineScore


def score(symbol: str, asof: date) -> EngineScore:
    """Skor sentimen agregat dari berita window terakhir.

    TODO(impl, Fase 2):
      - ambil berita symbol dgn available_at dalam window (mis. 3 hari).
      - rata-rata tertimbang sentimen (recency weighting).
      - confidence 'low' bila jumlah berita sedikit.
    """
    raise NotImplementedError("Implementasi di Fase 2.")
