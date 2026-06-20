"""Backtest engine fundamental — point-in-time, RIGOR penuh.

Dua uji jujur:
  1. RAW: skor fundamental apa adanya.
  2. SECTOR-NEUTRAL: skor di-demean per (tanggal, sektor) -> menjawab "ini faktor
     quality nyata, atau cuma taruhan sektor (mis. tech)?".
Keduanya lewat walk-forward (pooled + per-periode OOS). VALIDATED = lolos uji
SECTOR-NEUTRAL (lebih ketat & jujur): edge harus bertahan setelah sektor dibuang.

Anti look-ahead: skor pakai filing `filed_at <= tanggal`.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import US_UNIVERSE, load_sectors
from src.backtest.engine import sector_neutralize, walk_forward_quantile
from src.features.fundamental import compute
from src.storage import db

HORIZON = 21
SAMPLE_STEP = 21


def _build_panel(con) -> pd.DataFrame:
    rows = []
    for s in US_UNIVERSE:
        ps = con.execute("SELECT date, close FROM prices WHERE symbol = ? ORDER BY date", [s]).df()
        if len(ps) < HORIZON + 5:
            continue
        ps["date"] = pd.to_datetime(ps["date"])
        fdf = con.execute(
            "SELECT period, metric, value, filed_at FROM fundamentals WHERE symbol = ?", [s]
        ).df()
        if fdf.empty:
            continue
        fdf["filed_at"] = pd.to_datetime(fdf["filed_at"])
        closes = ps["close"].to_numpy()
        dates = ps["date"].to_numpy()
        for i in range(0, len(ps) - HORIZON, SAMPLE_STEP):
            d = pd.Timestamp(dates[i])
            avail = fdf.loc[fdf["filed_at"] <= d, ["period", "metric", "value"]]
            if avail.empty:
                continue
            res = compute(s, avail, float(closes[i]))
            if not res or res.get("score") is None:
                continue
            rows.append({"symbol": s, "date": d, "score": res["score"],
                         "fwd": (closes[i + HORIZON] / closes[i] - 1.0) * 100})
    return pd.DataFrame(rows)


def _report(label: str, res: dict) -> None:
    p = res["pooled"]
    print(f"\n[{label}] pooled spread={p.get('spread'):+.2f}% t={p.get('t_stat')} | per-periode:")
    for f in res["folds"]:
        tag = " (OOS terlama)" if f["k"] == 1 else ""
        print(f"   periode {f['k']} [{f['lo']}..{f['hi']}] spread={f['spread']:+.2f}% t={f['t']}{tag}")
    print(f"   >> {'VALID ✓' if res['validated'] else 'TOLAK ✗'}")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    panel = _build_panel(con)
    n_sym = panel["symbol"].nunique() if not panel.empty else 0
    print(f"=== BACKTEST FUNDAMENTAL · {n_sym} simbol · {len(panel)} obs point-in-time · {HORIZON}h ===")
    if panel.empty:
        con.close(); return

    raw = walk_forward_quantile(panel, n_folds=3, n_quantiles=5)
    neu = walk_forward_quantile(sector_neutralize(panel, load_sectors()), n_folds=3, n_quantiles=5)
    _report("RAW", raw)
    _report("SECTOR-NEUTRAL", neu)

    validated = neu["validated"]  # uji jujur: harus bertahan tanpa sektor
    p = neu["pooled"]
    note = (f"sector-neutral LOLOS walk-forward (pooled +{p['spread']:.2f}%, positif 3/3 periode)"
            if validated else
            f"sector-neutral TOLAK (pooled {p.get('spread'):+.2f}%); edge raw mungkin sebagian taruhan sektor")
    print(f"\n>> VONIS FUNDAMENTAL (basis sector-neutral): {'VALID ✓' if validated else 'TOLAK ✗'} — {note}")

    db.upsert_df(con, "validation", pd.DataFrame([{
        "engine": "fundamental", "horizon_days": HORIZON, "as_of": date.today(),
        "n_obs": int(p.get("n_obs", 0)), "top_mean": p.get("top_mean"),
        "bottom_mean": p.get("bottom_mean"), "spread": p.get("spread"),
        "t_stat": p.get("t_stat"), "validated": validated, "note": note,
    }]), ["engine", "horizon_days"])
    con.close()


if __name__ == "__main__":
    run()
