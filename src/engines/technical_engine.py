"""Technical Engine (Lapisan 5b).

Menghasilkan EngineScore 0..100 dari indikator teknikal (src/features/technical.py).
Confidence 'low' jika histori belum cukup (SMA200 belum terbentuk).

Aturan doktrin (docs/05_backtesting.md): skor ini DITAMPILKAN, tapi bobotnya di
composite hanya dipercaya setelah backtest membuktikan edge. Backtest dijalankan
via jobs/backtest_technical.py.
"""
from __future__ import annotations

import pandas as pd

from src.features.technical import indicators
from src.types import EngineScore


def _r(x, nd=1):
    return round(float(x), nd) if pd.notna(x) else None


def score(symbol: str, prices_df: pd.DataFrame) -> EngineScore:
    """Hitung skor teknikal dari deret harga (kolom ['date','close',...])."""
    ind = indicators(prices_df)
    row = ind.iloc[-1]
    as_of = pd.Timestamp(row["date"]).date()
    have_200 = pd.notna(row["sma200"])

    components = {
        "trend": _r(row["score_trend"]),
        "momentum_3m": _r(row["score_mom"]),
        "rsi_posture": _r(row["score_rsi"]),
        "rsi14": _r(row["rsi14"]),
        "ret_3m_pct": _r(row["ret63"], 2),
    }
    sc = float(row["tech_score"]) if pd.notna(row["tech_score"]) else 50.0

    return EngineScore(
        symbol=symbol,
        as_of=as_of,
        engine="technical",
        score=round(sc, 2),
        components=components,
        sample_size=None,
        confidence="normal" if have_200 else "low",
    )
