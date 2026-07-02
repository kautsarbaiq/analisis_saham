"""Backtest faktor di pasar IDX — vonis dipersist per-market (market='IDX').

Menguji sinyal yang sama seperti US pada universe LQ45: mean_reversion, event_drift,
bandarmology-proxy. Kuantil TERTIL (universe kecil), raw walk-forward OOS.
CATATAN: tanpa sector-neutral (tak ada peta sektor IDX di sistem) — vonis IDX adalah
raw-only, dinyatakan di note.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import IDX_UNIVERSE
from src.backtest.engine import build_panel, walk_forward_quantile
from src.storage import db

TESTS = [
    ("mr_score", "mean_reversion", [5, 10]),
    ("event_drift_score", "event_drift", [21, 63]),
    ("bandar_score", "bandarmology", [10, 21]),
]


def run() -> None:
    con = db.connect(); db.init_schema(con)
    prices = {}
    for s in IDX_UNIVERSE:
        df = con.execute(db.ADJ_PRICES_SQL, [s]).df()
        if len(df) >= 280:
            prices[s] = df
    print(f"=== BACKTEST IDX (LQ45) · {len(prices)} simbol · tertil, raw walk-forward ===")

    rows = []
    for score_col, engine, horizons in TESTS:
        for h in horizons:
            panel = build_panel(prices, horizon=h, score_col=score_col)
            r = walk_forward_quantile(panel, n_folds=3, n_quantiles=3)
            p = r["pooled"]
            fs = [round(f["spread"], 2) for f in r["folds"]]
            validated = r["validated"]
            note = (f"IDX raw walk-forward (tanpa sector-neutral): per-periode {fs}"
                    + ("" if validated else " — tolak"))
            print(f"  {engine:16} h{h:<3} spread={p.get('spread', 0):+.2f}% "
                  f"t={p.get('t_stat', 0):+.2f} periode={fs} "
                  f"{'VALID ✓' if validated else 'tolak'}")
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
