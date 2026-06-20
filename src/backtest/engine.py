"""Backtesting Engine (Lapisan 4) — lapisan kejujuran sistem.

Uji utama Fase 1: QUANTILE TEST — apakah saham ber-skor tinggi benar-benar
outperform yang ber-skor rendah pada return ke depan? Jika tidak terukur, skor
belum boleh dipercaya (docs/05_backtesting.md).

Anti-bias yang diterapkan:
  - look-ahead: skor pada T hanya pakai data <= T; fwd return pakai T+horizon.
  - histori penuh: baris dengan SMA200 belum terbentuk dibuang (skor belum stabil).
  - survivorship: CATATAN — universe = saham yang masih hidup; backtest ini
    cenderung optimistis. Ditandai jujur di output runner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.metrics import welch_t
from src.features.technical import indicators


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    """Return % dari T ke T+horizon (target prediksi)."""
    return (close.shift(-horizon) / close - 1.0) * 100


def build_panel(
    prices_by_symbol: dict[str, pd.DataFrame],
    horizon: int = 5,
    score_col: str = "tech_score",
) -> pd.DataFrame:
    """Bangun panel (symbol, date, score, fwd) dari banyak saham — siap quantile test."""
    frames = []
    for sym, df in prices_by_symbol.items():
        ind = indicators(df)
        ind["fwd"] = forward_return(ind["close"], horizon)
        sub = ind.loc[ind["sma200"].notna(), ["date", score_col, "fwd"]].copy()
        sub = sub.dropna(subset=[score_col, "fwd"])
        sub["symbol"] = sym
        frames.append(sub.rename(columns={score_col: "score"}))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def quantile_test(panel: pd.DataFrame, n_quantiles: int = 5) -> dict:
    """Bagi observasi ke kuantil skor; bandingkan return ke depan tiap kuantil.

    Kembalikan ringkasan terukur: mean fwd return per kuantil, spread top-bottom,
    win-rate tiap ujung, dan statistik t Welch (top vs bottom).
    """
    if panel.empty:
        return {}
    p = panel.copy()
    p["q"] = pd.qcut(p["score"], n_quantiles, labels=False, duplicates="drop")

    buckets = []
    for q, grp in p.groupby("q"):
        buckets.append({
            "q": int(q),
            "mean_fwd": round(float(grp["fwd"].mean()), 3),
            "win_rate": round(float((grp["fwd"] > 0).mean()), 3),
            "n": int(len(grp)),
        })

    qmax, qmin = p["q"].max(), p["q"].min()
    top = p.loc[p["q"] == qmax, "fwd"]
    bot = p.loc[p["q"] == qmin, "fwd"]
    return {
        "n_obs": int(len(p)),
        "n_quantiles": int(p["q"].nunique()),
        "buckets": buckets,
        "top_mean": round(float(top.mean()), 3),
        "bottom_mean": round(float(bot.mean()), 3),
        "spread": round(float(top.mean() - bot.mean()), 3),
        "top_win": round(float((top > 0).mean()), 3),
        "bottom_win": round(float((bot > 0).mean()), 3),
        "t_stat": round(welch_t(top.to_numpy(), bot.to_numpy()), 3),
    }
