"""Backtest sinyal short-volume FINRA — hipotesis A-PRIORI (dikunci sebelum hasil).

H1 `shortvol_level`: short seller ter-informasi (Boehmer dkk.) -> SVR (short/total,
   rata-rata 5 hari) RENDAH = bullish. score = (1 - svr5) * 100.
H2 `shortvol_chg`  : tekanan shorting MEREDA vs baseline -> bullish.
   score = clip(50 - (svr5 - svr63) * 250).

Rigor standar proyek: harga ter-adjust, kuantil per-tanggal, walk-forward OOS
3 periode, raw + sector-neutral; GERBANG = sector-neutral. Vonis -> tabel validation
(market='US'). Tidak ada tuning parameter setelah melihat hasil (anti p-hacking).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import US_UNIVERSE, load_sectors
from src.backtest.engine import sector_neutralize, walk_forward_quantile
from src.storage import db

HORIZONS = [21, 63]
# Lag 1 hari perdagangan: data FINRA hari-D terbit pagi D+1. Skor pakai SVR s/d
# hari SEBELUM entry -> nol look-ahead publikasi. Ini versi jujur (non-negosiasi).
LAG = 1


def _panels(con) -> dict[str, pd.DataFrame]:
    sv = con.execute("SELECT symbol, date, short_vol, total_vol FROM short_volume "
                     "ORDER BY symbol, date").df()
    if sv.empty:
        return {}
    sv["date"] = pd.to_datetime(sv["date"])

    out: dict[str, list] = {"shortvol_level": [], "shortvol_chg": []}
    fwd_frames: dict[int, list] = {h: [] for h in HORIZONS}
    for sym in US_UNIVERSE:
        px = con.execute(db.ADJ_PRICES_SQL, [sym]).df()[["date", "close"]]
        if len(px) < 300:
            continue
        px["date"] = pd.to_datetime(px["date"])
        s = sv[sv["symbol"] == sym][["date", "short_vol", "total_vol"]]
        if len(s) < 300:
            continue
        m = px.merge(s, on="date", how="left")
        svr = (m["short_vol"] / m["total_vol"]).clip(0, 1)
        svr5 = svr.rolling(5, min_periods=3).mean()
        svr63 = svr.rolling(63, min_periods=40).mean()
        # LAG: skor pada baris T memakai data s/d T-LAG (anti look-ahead publikasi).
        lvl = ((1 - svr5) * 100).clip(0, 100).shift(LAG)
        chg = (50 - (svr5 - svr63) * 250).clip(0, 100).shift(LAG)
        for h in HORIZONS:
            fwd = (m["close"].shift(-h) / m["close"] - 1.0) * 100
            base = pd.DataFrame({"symbol": sym, "date": m["date"], "fwd": fwd})
            out["shortvol_level"].append(base.assign(score=lvl, h=h))
            out["shortvol_chg"].append(base.assign(score=chg, h=h))

    return {k: pd.concat(v, ignore_index=True).dropna(subset=["score", "fwd"])
            for k, v in out.items() if v}


def _fmt(r) -> str:
    p = r["pooled"]
    fs = [round(f["spread"], 2) for f in r["folds"]]
    return (f"spread={p.get('spread', 0):+.2f}% t={p.get('t_stat', 0):+.2f} "
            f"periode={fs} {'VALID ✓' if r['validated'] else 'tolak'}")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    sectors = load_sectors()
    panels = _panels(con)
    if not panels:
        print("Tabel short_volume kosong — jalankan jobs.shortvol_ingest dulu.")
        con.close(); return

    rows = []
    for engine, pall in panels.items():
        print(f"\n===== {engine} · {pall['symbol'].nunique()} simbol =====")
        for h in HORIZONS:
            panel = pall[pall["h"] == h][["symbol", "date", "score", "fwd"]]
            raw = walk_forward_quantile(panel, n_folds=3, n_quantiles=5)
            neu = walk_forward_quantile(sector_neutralize(panel, sectors),
                                        n_folds=3, n_quantiles=5)
            print(f"  h{h:<3} RAW {_fmt(raw)}")
            print(f"       SN  {_fmt(neu)}")
            p = neu["pooled"]
            fs = [round(f["spread"], 2) for f in neu["folds"]]
            note = (f"FINRA short-volume, hipotesis a-priori; SN per-periode {fs}; "
                    f"raw pooled {raw['pooled'].get('spread'):+.2f}%"
                    + ("" if neu["validated"] else " — tolak"))
            rows.append({
                "engine": engine, "horizon_days": h, "market": "US",
                "as_of": date.today(), "n_obs": int(p.get("n_obs", 0)),
                "top_mean": p.get("top_mean"), "bottom_mean": p.get("bottom_mean"),
                "spread": p.get("spread"), "t_stat": p.get("t_stat"),
                "validated": neu["validated"], "note": note,
            })

    db.upsert_df(con, "validation", pd.DataFrame(rows),
                 ["engine", "horizon_days", "market"])
    val = con.execute("SELECT engine, horizon_days FROM validation "
                      "WHERE market='US' AND validated=TRUE").fetchall()
    print(f"\nUS tervalidasi kini: {val}")
    con.close()


if __name__ == "__main__":
    run()
