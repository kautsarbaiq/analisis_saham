"""Backtest faktor di pasar IDX — vonis dipersist per-market (market='IDX').

Menguji sinyal yang sama seperti US pada universe LQ45: mean_reversion, event_drift,
bandarmology-proxy. Kuantil TERTIL per-tanggal (universe kecil), walk-forward OOS.

Kini dgn SECTOR-NEUTRAL (peta IDX_SECTORS manual, ~8 bucket): gerbang validated =
vonis sector-neutral — konsisten dgn gerbang event_drift di US (edge-nya dalam-sektor)
dan dgn cara produksi men-demean skor per market+sektor. Vonis raw dilaporkan sbg info.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import IDX_UNIVERSE, load_sectors
from src.backtest.engine import build_panel, sector_neutralize, walk_forward_quantile
from src.storage import db

TESTS = [
    ("mr_score", "mean_reversion", [5, 10]),
    ("event_drift_score", "event_drift", [21, 63]),
    ("bandar_score", "bandarmology", [10, 21]),
]


def _fmt(r) -> str:
    p = r["pooled"]
    fs = [round(f["spread"], 2) for f in r["folds"]]
    return (f"spread={p.get('spread', 0):+.2f}% t={p.get('t_stat', 0):+.2f} "
            f"periode={fs} {'VALID ✓' if r['validated'] else 'tolak'}")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    sectors = load_sectors()
    prices = {}
    for s in IDX_UNIVERSE:
        df = con.execute(db.ADJ_PRICES_SQL, [s]).df()
        if len(df) >= 280:
            prices[s] = df
    print(f"=== BACKTEST IDX (LQ45) · {len(prices)} simbol · tertil per-tanggal · "
          f"raw + sector-neutral ({len(set(sectors[s] for s in prices))} sektor) ===")

    rows = []
    for score_col, engine, horizons in TESTS:
        for h in horizons:
            panel = build_panel(prices, horizon=h, score_col=score_col)
            raw = walk_forward_quantile(panel, n_folds=3, n_quantiles=3)
            neu = walk_forward_quantile(sector_neutralize(panel, sectors),
                                        n_folds=3, n_quantiles=3)
            print(f"  {engine:16} h{h:<3} RAW {_fmt(raw)}")
            print(f"  {'':16}      SN  {_fmt(neu)}")
            validated = neu["validated"]  # gerbang = sector-neutral (konsisten US)
            p = neu["pooled"]
            fs = [round(f["spread"], 2) for f in neu["folds"]]
            note = (f"IDX sector-neutral walk-forward: per-periode {fs}; "
                    f"raw pooled {raw['pooled'].get('spread'):+.2f}%"
                    + ("" if validated else " — tolak"))
            rows.append({
                "engine": engine, "horizon_days": h, "market": "IDX",
                "as_of": date.today(), "n_obs": int(p.get("n_obs", 0)),
                "top_mean": p.get("top_mean"), "bottom_mean": p.get("bottom_mean"),
                "spread": p.get("spread"), "t_stat": p.get("t_stat"),
                "validated": validated, "note": note,
            })

    db.upsert_df(con, "validation", pd.DataFrame(rows),
                 ["engine", "horizon_days", "market"])
    val = con.execute(
        "SELECT engine, horizon_days FROM validation WHERE market='IDX' AND validated=TRUE"
    ).fetchall()
    print(f"\nIDX tervalidasi: {val or 'tidak ada'}")
    con.close()


if __name__ == "__main__":
    run()
