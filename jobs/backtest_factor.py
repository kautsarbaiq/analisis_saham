"""Backtest generik faktor teknikal — rigor penuh (walk-forward OOS + sector-neutral).

Menguji score_col apa pun dari features.technical.indicators dengan standar yang sama
seperti mean-reversion: harus lolos walk-forward (positif di SEMUA periode termasuk
OOS terlama) SETELAH sector-neutralization. Persist vonis ke tabel `validation`.

Pakai: python -m jobs.backtest_factor <score_col> <engine_name> <h1,h2,...>
Contoh: python -m jobs.backtest_factor lowvol_score low_volatility 21,63
"""
from __future__ import annotations

import sys
from datetime import date

import pandas as pd

from config.universe import US_UNIVERSE, load_sectors
from src.backtest.engine import build_panel, sector_neutralize, walk_forward_quantile
from src.storage import db


def _prices(con) -> dict:
    out = {}
    for s in US_UNIVERSE:
        df = con.execute(db.ADJ_PRICES_SQL, [s]).df()
        if len(df) >= 280:
            out[s] = df
    return out


def _report(label: str, res: dict) -> None:
    p = res["pooled"]
    print(f"\n[{label}] pooled spread={p.get('spread'):+.2f}% t={p.get('t_stat')} | per-periode:")
    for f in res["folds"]:
        tag = " (OOS terlama)" if f["k"] == 1 else ""
        print(f"   periode {f['k']} [{f['lo']}..{f['hi']}] spread={f['spread']:+.2f}% t={f['t']}{tag}")
    print(f"   >> {'VALID ✓' if res['validated'] else 'TOLAK ✗'}")


def run(score_col: str, engine: str, horizons: list[int], market: str = "US") -> None:
    con = db.connect(); db.init_schema(con)
    prices = _prices(con)
    sectors = load_sectors()
    print(f"=== BACKTEST FAKTOR '{engine}' (score_col={score_col}, market={market}) · {len(prices)} simbol ===")

    rows = []
    for h in horizons:
        panel = build_panel(prices, horizon=h, score_col=score_col)
        raw = walk_forward_quantile(panel, n_folds=3, n_quantiles=5)
        neu = walk_forward_quantile(sector_neutralize(panel, sectors), n_folds=3, n_quantiles=5)
        print(f"\n----- horizon {h}h -----")
        _report("RAW", raw)
        _report("SECTOR-NEUTRAL", neu)
        validated = neu["validated"]
        p = neu["pooled"]
        note = ("sector-neutral LOLOS walk-forward" if validated
                else f"sector-neutral TOLAK (pooled {p.get('spread'):+.2f}%, t {p.get('t_stat')})")
        print(f">> VONIS {engine} h{h}: {'VALID ✓' if validated else 'TOLAK ✗'} — {note}")
        rows.append({
            "engine": engine, "horizon_days": h, "market": market, "as_of": date.today(),
            "n_obs": int(p.get("n_obs", 0)), "top_mean": p.get("top_mean"),
            "bottom_mean": p.get("bottom_mean"), "spread": p.get("spread"),
            "t_stat": p.get("t_stat"), "validated": validated, "note": note,
        })

    db.upsert_df(con, "validation", pd.DataFrame(rows), ["engine", "horizon_days", "market"])
    con.close()


if __name__ == "__main__":
    sc = sys.argv[1] if len(sys.argv) > 1 else "lowvol_score"
    en = sys.argv[2] if len(sys.argv) > 2 else "low_volatility"
    hz = [int(x) for x in (sys.argv[3].split(",") if len(sys.argv) > 3 else ["21", "63"])]
    run(sc, en, hz)
