"""Mean-Reversion Engine — engine TERVALIDASI pertama (lihat jobs/backtest_mean_reversion.py).

Skor mr_score (oversold-ness) terbukti punya edge kecil tapi konsisten out-of-sample
(Q4 oversold memantul di 3/3 periode 5 tahun). Karena lolos gerbang `validation`,
inilah engine pertama yang BOLEH menyetir skor prediktif composite.

Edge realistis & kecil (+0.18-0.24% per 5-10 hari) dan melemah dari waktu ke waktu —
ditampilkan apa adanya, bukan dijanjikan besar.
"""
from __future__ import annotations

import pandas as pd

from src.features.technical import indicators
from src.types import EngineScore


def _r(x, nd=1):
    return round(float(x), nd) if pd.notna(x) else None


def score(symbol: str, prices_df: pd.DataFrame) -> EngineScore:
    """Skor mean-reversion (0..100, tinggi = oversold/menarik utk pantulan)."""
    ind = indicators(prices_df)
    row = ind.iloc[-1]
    have = pd.notna(row["mr_score"])

    components = {
        "reversal": _r(row["score_rev"]),
        "oversold": _r(row["score_oversold"]),
        "below_ma": _r(row["score_below_ma"]),
        "ret_1m_pct": _r(row["ret21"], 2),
        "rsi14": _r(row["rsi14"]),
    }
    sc = float(row["mr_score"]) if have else 50.0

    return EngineScore(
        symbol=symbol,
        as_of=pd.Timestamp(row["date"]).date(),
        engine="mean_reversion",
        score=round(sc, 2),
        components=components,
        sample_size=None,
        confidence="normal" if have else "low",
    )
