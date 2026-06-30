"""Bandarmology Engine (Lapisan 5d) — IDX, PROXY GRATIS (deskriptif).

Skor akumulasi/distribusi via Chaikin A/D Line (volume-based). CATATAN JUJUR: backtest
IDX menunjukkan proxy ini TIDAK punya edge (malah kontrarian) -> ia DESKRIPTIF saja,
BUKAN sinyal beli tervalidasi. Bandarmology sejati butuh broker-summary berbayar
(Stockbit/RTI). Ditampilkan sebagai konteks "akumulasi/distribusi", bukan untuk
menyetir skor prediktif.
"""
from __future__ import annotations

import pandas as pd

from src.features.technical import indicators
from src.types import EngineScore


def score(symbol: str, prices_df: pd.DataFrame) -> EngineScore:
    ind = indicators(prices_df)
    row = ind.iloc[-1]
    have = pd.notna(row["bandar_score"])
    return EngineScore(
        symbol=symbol,
        as_of=pd.Timestamp(row["date"]).date(),
        engine="bandarmology",
        score=round(float(row["bandar_score"]), 2) if have else 50.0,
        components={"acc_1m": round(float(row["bandar_acc"]), 4) if pd.notna(row["bandar_acc"]) else None},
        sample_size=None,
        confidence="low",  # proxy gratis: selalu low-confidence
    )
