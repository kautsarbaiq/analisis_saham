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


def sector_neutralize(panel: pd.DataFrame, sectors: dict[str, str]) -> pd.DataFrame:
    """Hilangkan komponen SEKTOR dari skor: demean per (tanggal, sektor).

    Menjawab "apakah edge ini faktor nyata atau cuma taruhan sektor?". Setelah
    netralisasi, skor mengukur posisi RELATIF dalam sektornya, bukan sektor mana.
    """
    p = panel.copy()
    p["sector"] = p["symbol"].map(lambda s: sectors.get(s, "?"))
    grp = p.groupby([p["date"], p["sector"]])["score"].transform("mean")
    p["score"] = p["score"] - grp + p["score"].mean()
    return p


def walk_forward_quantile(panel: pd.DataFrame, n_folds: int = 3,
                          n_quantiles: int = 5, t_threshold: float = 2.0) -> dict:
    """Uji rigor: quantile test pooled + per-PERIODE (walk-forward lintas waktu).

    validated HANYA jika: pooled signifikan (t>threshold) DAN spread positif di
    SEMUA periode termasuk yang TERLAMA (out-of-sample sejati). Mencegah edge yang
    cuma artefak satu rezim. Catatan: t pooled menggelembung krn observasi tumpang-
    tindih; konsistensi antar-periode adalah bukti yang lebih bermakna.
    """
    if panel.empty:
        return {"validated": False, "pooled": {}, "folds": []}
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"])
    pooled = quantile_test(p, n_quantiles)

    dts = p["date"].sort_values().unique()
    cuts = [dts[0]] + [dts[len(dts) * k // n_folds] for k in range(1, n_folds)] + [dts[-1]]
    folds = []
    for k in range(n_folds):
        lo, hi = cuts[k], cuts[k + 1]
        fr = quantile_test(p[(p["date"] >= lo) & (p["date"] <= hi)], n_quantiles)
        folds.append({"k": k + 1, "lo": str(pd.Timestamp(lo).date()),
                      "hi": str(pd.Timestamp(hi).date()),
                      "spread": fr.get("spread"), "t": fr.get("t_stat"), "n": fr.get("n_obs")})

    fs = [f["spread"] for f in folds if f["spread"] is not None]
    validated = bool(
        pooled.get("spread", 0) > 0 and pooled.get("t_stat", 0) > t_threshold
        and len(fs) == n_folds and all(s > 0 for s in fs)
    )
    return {"validated": validated, "pooled": pooled, "folds": folds,
            "early_spread": fs[0] if fs else None}
