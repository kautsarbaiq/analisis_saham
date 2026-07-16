"""Short-Volume Engine — sinyal ke-2 US TERVALIDASI (FINRA Reg SHO).

Skor = (1 - SVR5) * 100, di mana SVR5 = rata-rata 5 hari rasio short-volume
(short_vol / total_vol). Rasio short RENDAH -> skor tinggi -> bullish (short seller
ter-informasi; Boehmer, Jones & Zhang 2008).

Vonis (rigor penuh, anti look-ahead lag-1, adversarial-verified): US sector-neutral
+0.39%/21h (t 9.8) & +1.67%/63h (t 24), monotonik Q0->Q4, robust lag/penny-stock.

PARITAS dgn definisi yang divalidasi (jobs/backtest_shortvol.py) — non-negosiasi:
  - hanya data ber-tanggal < as_of (lag-1 publikasi FINRA; audit: versi lama memakai
    tail(5) tanpa potongan sehingga skor as_of lama bisa bocor data masa depan);
  - window 5 baris terakhir dalam <=12 hari kalender sebelum as_of (cermin
    rolling(5, min_periods=3) di grid hari bursa);
  - <3 observasi ATAU data terakhir >7 hari sebelum as_of -> kembalikan None:
    TIDAK ADA skor (bukan placeholder 50) — placeholder mencemari mean sektor dan
    menyetir composite tanpa data (pelanggaran aturan "tanpa opini tanpa data").

Di produksi skornya di-sector-neutralkan cross-sectional per market (seperti
event_drift). US-only (data FINRA = pasar AS).
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src.types import EngineScore

MAX_LAG_DAYS = 7     # data terakhir lebih tua dari ini vs as_of -> tak ada skor
WINDOW_DAYS = 12     # ~5 hari bursa + buffer libur (cermin window rolling backtest)
MIN_OBS = 3          # cermin min_periods=3 pada backtest


def score(symbol: str, sv_df: pd.DataFrame | None, as_of: date) -> EngineScore | None:
    """sv_df: baris short_volume (date, short_vol, total_vol) utk satu simbol.

    Kembalikan None bila data tak cukup/terlalu tua utk as_of — engine ini lalu
    tidak ikut composite (renormalisasi otomatis di combine) maupun mean sektor.
    """
    if sv_df is None or sv_df.empty:
        return None
    ts = pd.Timestamp(as_of)
    d = sv_df.sort_values("date")
    d = d[(d["date"] < ts) & (d["date"] >= ts - pd.Timedelta(days=WINDOW_DAYS))]
    d = d[d["total_vol"] > 0]
    if len(d) < MIN_OBS:
        return None
    last = d["date"].max()
    if (ts - last).days > MAX_LAG_DAYS:
        return None
    w = d.tail(5)
    svr5 = float((w["short_vol"] / w["total_vol"]).clip(0, 1).mean())
    return EngineScore(
        symbol=symbol, as_of=as_of, engine="shortvol_level",
        score=round((1 - svr5) * 100, 2),
        components={"svr5": round(svr5, 3), "n_days": int(len(w)),
                    "data_lag_days": int((ts - last).days)},
        sample_size=None, confidence="normal",
    )
