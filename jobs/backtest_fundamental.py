"""Backtest engine fundamental — point-in-time, anti look-ahead.

Untuk tiap tanggal sampel (bulanan) & tiap simbol: hitung skor fundamental HANYA
dari filing yang `filed_at <= tanggal` (point-in-time), lalu ukur return ke depan.
Quantile test lintas-simbol menilai: apakah saham fundamental-bagus outperform?

GERBANG KEJUJURAN (penting): dengan universe 15 saham, skor fundamental nyaris
konstan per simbol -> N efektif ~= jumlah simbol, JAUH lebih kecil dari N mentah.
Maka validated butuh `n_symbols >= MIN_SYMBOLS`; di bawah itu hasilnya UNDERPOWERED
dan otomatis ditolak (apa pun spread-nya). Ini memotivasi perluasan universe (S&P 500).
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.backtest.engine import quantile_test
from src.features.fundamental import compute
from src.storage import db

HORIZON = 21
SAMPLE_STEP = 21          # ~bulanan (hari perdagangan)
MIN_SYMBOLS = 30          # ambang power minimal agar vonis dipercaya
N_QUANTILES = 3           # universe kecil -> tertil, bukan kuintil


def run() -> None:
    con = db.connect()
    db.init_schema(con)

    syms = [r[0] for r in con.execute("SELECT DISTINCT symbol FROM fundamentals").fetchall()]
    rows = []
    for s in syms:
        ps = con.execute("SELECT date, close FROM prices WHERE symbol = ? ORDER BY date", [s]).df()
        if len(ps) < HORIZON + 5:
            continue
        ps["date"] = pd.to_datetime(ps["date"])
        fdf = con.execute(
            "SELECT period, metric, value, filed_at FROM fundamentals WHERE symbol = ?", [s]
        ).df()
        fdf["filed_at"] = pd.to_datetime(fdf["filed_at"])
        closes = ps["close"].to_numpy()
        dates = ps["date"].to_numpy()

        for i in range(0, len(ps) - HORIZON, SAMPLE_STEP):
            d = pd.Timestamp(dates[i])
            fwd = (closes[i + HORIZON] / closes[i] - 1.0) * 100
            avail = fdf.loc[fdf["filed_at"] <= d, ["period", "metric", "value"]]
            if avail.empty:
                continue
            res = compute(s, avail, float(closes[i]))
            if not res or res.get("score") is None:
                continue
            rows.append({"symbol": s, "date": d, "score": res["score"], "fwd": fwd})

    panel = pd.DataFrame(rows)
    n_symbols = panel["symbol"].nunique() if not panel.empty else 0
    res = quantile_test(panel, n_quantiles=N_QUANTILES) if not panel.empty else {}

    print(f"\n=== BACKTEST ENGINE FUNDAMENTAL · {n_symbols} simbol · {len(panel)} obs point-in-time ===")
    if not res:
        print("Tidak cukup data."); con.close(); return
    for b in res["buckets"]:
        print(f"  Q{b['q']}  mean_fwd={b['mean_fwd']:+.2f}%  win={b['win_rate']*100:4.1f}%  n={b['n']}")
    print(f"  >> top={res['top_mean']:+.2f}%  bottom={res['bottom_mean']:+.2f}%  "
          f"spread={res['spread']:+.2f}%  t={res['t_stat']}")

    underpowered = n_symbols < MIN_SYMBOLS
    validated = bool(res["spread"] > 0 and res["t_stat"] > 2.0 and not underpowered)
    if underpowered:
        note = (f"UNDERPOWERED: hanya {n_symbols} simbol (<{MIN_SYMBOLS}); skor "
                f"fundamental nyaris konstan/simbol -> N efektif kecil. Spread "
                f"{res['spread']:+.2f}% TIDAK dapat dipercaya. Perluas universe dulu.")
    else:
        note = "edge positif terukur" if validated else f"tidak ada edge (spread {res['spread']:+.2f}%)"
    print(f"  >> VONIS: {'VALID ✓' if validated else 'TOLAK ✗'} — {note}")

    db.upsert_df(con, "validation", pd.DataFrame([{
        "engine": "fundamental", "horizon_days": HORIZON, "as_of": date.today(),
        "n_obs": int(len(panel)), "top_mean": res["top_mean"], "bottom_mean": res["bottom_mean"],
        "spread": res["spread"], "t_stat": res["t_stat"], "validated": validated, "note": note,
    }]), ["engine", "horizon_days"])
    con.close()


if __name__ == "__main__":
    run()
