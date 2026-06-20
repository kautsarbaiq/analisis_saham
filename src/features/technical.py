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

    # --- Faktor LOW-VOLATILITY (anomali low-vol; vol rendah -> skor tinggi) ---
    out["ret1d"] = c.pct_change(1, fill_method=None)
    out["vol63"] = out["ret1d"].rolling(63).std() * (252 ** 0.5)      # volatilitas tahunan
    out["lowvol_score"] = _clip((0.55 - out["vol63"]) / (0.55 - 0.15) * 100)  # 15% -> 100, 55% -> 0

    # --- EVENT-DRIFT (PEAD proxy): kejutan harga pada hari ber-VOLUME tinggi =
    # proxy "ada berita". Hipotesis: gerakan news-driven cenderung lanjut (drift),
    # beda dari noise yg mean-revert. Skor tinggi = baru ada dorongan positif.
    out["vol_ratio"] = out["volume"] / out["volume"].rolling(20).mean()
    _hv = (out["vol_ratio"] > 1.5).astype(float)
    out["event_ret"] = (out["ret1d"] * _hv).rolling(10).sum() * 100   # net % gerak hari hi-vol, 10h
    out["event_drift_score"] = _clip(50 + out["event_ret"] * 3)       # +16% net -> 100
    return out
