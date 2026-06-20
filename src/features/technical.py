"""Feature store teknikal (Lapisan 3) — indikator + sub-skor.

Satu sumber kebenaran untuk indikator teknikal, dipakai BERSAMA oleh:
  - technical_engine (skor live untuk dashboard), dan
  - backtest engine (skor historis untuk uji edge).
Memakai fungsi yang sama menjamin skor live == skor yang di-backtest (tidak ada
divergensi diam-diam). Semua indikator pada tanggal T hanya memakai data <= T
(rolling), jadi tidak ada look-ahead.
"""
from __future__ import annotations

import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI Wilder (EWM)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def _clip(s: pd.Series, lo: float = 0, hi: float = 100) -> pd.Series:
    return s.clip(lo, hi)


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung indikator + sub-skor untuk seluruh deret harga.

    Input: df dengan kolom minimal ['date', 'close'] terurut menaik.
    Output: salinan df + kolom sma20/50/200, rsi14, ret63, sub-skor, dan `tech_score`.

    Filosofi skor (transparan & dapat di-audit): technical_score = rata-rata dari
    3 sub-skor 0..100 — tren, momentum 3-bulan, dan postur RSI. NILAI INI BELUM
    DIPERCAYA sampai dibuktikan punya edge oleh backtest (lihat docs/05_backtesting.md).
    """
    out = df.copy().reset_index(drop=True)
    c = out["close"]

    out["sma20"] = c.rolling(20).mean()
    out["sma50"] = c.rolling(50).mean()
    out["sma200"] = c.rolling(200).mean()
    out["rsi14"] = rsi(c, 14)
    out["ret63"] = c.pct_change(63, fill_method=None) * 100  # ~3 bulan, %

    # Sub-skor 1: keselarasan tren (0..100) — berapa banyak kondisi bullish terpenuhi.
    out["score_trend"] = (
        (c > out["sma20"]).astype(float)
        + (c > out["sma50"]).astype(float)
        + (c > out["sma200"]).astype(float)
        + (out["sma20"] > out["sma50"]).astype(float)
        + (out["sma50"] > out["sma200"]).astype(float)
    ) / 5 * 100

    # Sub-skor 2: momentum 3-bulan, dipetakan ke 0..100 (+20% -> 100, -20% -> 0).
    out["score_mom"] = _clip(50 + out["ret63"] * 2.5)

    # Sub-skor 3: postur RSI — hadiahi momentum konstruktif, hukum ekstrem (>65 / <35).
    rsiv = out["rsi14"]
    out["score_rsi"] = _clip(
        100 - (rsiv - 65).clip(lower=0) * 3 - (35 - rsiv).clip(lower=0) * 3
    )

    out["tech_score"] = (out["score_trend"] + out["score_mom"] + out["score_rsi"]) / 3

    # --- Sinyal MEAN-REVERSION (a-priori; fokus 'oversold', kebalikan momentum) ---
    # Konstruksi sengaja BERBEDA dari tech_score: menargetkan saham tertekan yang
    # cenderung memantul, bukan kekuatan tren. Diuji terpisah & out-of-sample.
    out["ret21"] = c.pct_change(21, fill_method=None) * 100          # ~1 bulan, %
    out["score_rev"] = _clip(50 - out["ret21"] * 2.5)                # turun 20% -> 100
    out["score_oversold"] = _clip((60 - out["rsi14"]) / 40 * 100)    # RSI 20 -> 100, 60 -> 0
    out["score_below_ma"] = _clip((out["sma20"] - c) / out["sma20"] * 1000)  # 10% di bawah -> 100
    out["mr_score"] = (out["score_rev"] + out["score_oversold"] + out["score_below_ma"]) / 3
    return out
