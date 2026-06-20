"""Fundamental Engine (Lapisan 5a) — analisis "ala huge fund" dari SEC EDGAR.

Bungkus features/fundamental.compute -> EngineScore 0..100. Sama doktrinnya dgn
teknikal: skor ini DESKRIPTIF sampai backtest membuktikan edge (gerbang `validation`).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.features.fundamental import compute
from src.types import EngineScore


def score(symbol: str, fundamentals_df: pd.DataFrame, price: float | None = None) -> EngineScore:
    """Skor fundamental + komponen audit (rasio, Piotroski, Altman Z)."""
    res = compute(symbol, fundamentals_df, price)
    if res is None or res.get("score") is None:
        return EngineScore(
            symbol=symbol, as_of=date.today(), engine="fundamental",
            score=50.0, components={"note": "data fundamental tak memadai"},
            sample_size=None, confidence="low",
        )

    as_of = pd.to_datetime(res["as_of_period"]).date()
    conf = "normal" if (res["years"] >= 2 and res["piotroski_avail"] >= 7) else "low"
    comp = {
        k: res[k] for k in (
            "piotroski", "altman_z", "roe", "net_margin", "op_margin",
            "rev_growth", "eps_growth", "current_ratio", "debt_to_equity",
        )
    }
    comp["sub_scores"] = res["sub_scores"]

    return EngineScore(
        symbol=symbol, as_of=as_of, engine="fundamental",
        score=res["score"], components=comp,
        sample_size=res["years"], confidence=conf,
    )
