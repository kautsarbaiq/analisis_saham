"""Feature store fundamental (Lapisan 3).

Ubah fakta mentah SEC EDGAR -> rasio & skor komposit terukur.
Semua perhitungan memakai data yang `filed_at <= asof` (anti look-ahead).
"""
from __future__ import annotations


def compute(symbol: str, fundamentals_df, prices_df):
    """Hitung rasio fundamental -> baris (symbol, date, name, value).

    TODO(impl, Fase 1):
      - Valuasi: P/E, P/B, P/S, EV/EBITDA (butuh harga + fundamental).
      - Kualitas: ROE, ROIC, margin (gross/op/net) + tren.
      - Kesehatan: Altman Z-Score, current ratio, debt/equity.
      - Skor akuntansi: Piotroski F-Score (0..9).
      - Pertumbuhan: CAGR revenue & EPS.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
