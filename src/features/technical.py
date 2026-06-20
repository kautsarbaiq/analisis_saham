"""Feature store teknikal (Lapisan 3).

Hitung indikator sekali, cache ke tabel `features`, reuse di technical engine & backtest.
Hindari look-ahead: indikator pada tanggal T hanya boleh memakai data <= T.
"""
from __future__ import annotations


def compute(symbol: str, prices_df):
    """Hitung indikator teknikal -> baris (symbol, date, name, value).

    TODO(impl, Fase 1): MA(20/50/200), RSI(14), MACD, Bollinger, ATR(14), OBV,
    ADX, volume_zscore. Pakai pandas-ta. Pastikan tidak ada leakage.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
