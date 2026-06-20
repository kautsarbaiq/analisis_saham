"""Deteksi regime pasar (Lapisan 3/5e).

Sinyal yang sama bisa berlawanan hasil di regime berbeda; matching event-study &
scoring memakai ini sebagai konteks. Lookback = REGIME_LOOKBACK_DAYS.
"""
from __future__ import annotations


def detect(benchmark_prices, macro_df=None) -> str:
    """Klasifikasi regime: 'bull_trend' | 'bear_trend' | 'sideways' | 'high_vol'.

    TODO(impl, Fase 1): pakai tren index (mis. SPX), realized vol, dan opsional
    sinyal makro (VIX, term spread). Kembalikan label + skor kepercayaan.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
