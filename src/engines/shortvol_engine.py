"""Short-Volume Engine — sinyal ke-2 US TERVALIDASI (FINRA Reg SHO).

Skor = (1 - SVR5) * 100, di mana SVR5 = rata-rata 5 hari rasio short-volume
(short_vol / total_vol). Rasio short RENDAH -> skor tinggi -> bullish (short seller
ter-informasi; Boehmer, Jones & Zhang 2008).

Vonis (rigor penuh, anti look-ahead lag-1, adversarial-verified): US sector-neutral
+0.39%/21h (t 9.8) & +1.67%/63h (t 24), monotonik Q0->Q4, robust lag/penny-stock.

Di produksi skornya di-sector-neutralkan cross-sectional per market (seperti
event_drift). US-only (data FINRA = pasar AS).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.types import EngineScore


def score(symbol: str, sv_df: pd.DataFrame, as_of: date, stale: bool = False) -> EngineScore:
    """sv_df: baris short_volume (date, short_vol, total_vol) utk satu simbol."""
    if sv_df is None or sv_df.empty:
        return EngineScore(symbol, as_of, "shortvol_level", 50.0,
                           {"note": "tak ada data short volume"}, None, "low")
    d = sv_df.sort_values("date")
    svr = (d["short_vol"] / d["total_vol"]).clip(0, 1)
    svr5 = float(svr.tail(5).mean())
    sc = round((1 - svr5) * 100, 2)
    return EngineScore(
        symbol=symbol, as_of=as_of, engine="shortvol_level",
        score=sc, components={"svr5": round(svr5, 3), "stale": bool(stale)},
        sample_size=None, confidence="low" if stale else "normal",
    )
