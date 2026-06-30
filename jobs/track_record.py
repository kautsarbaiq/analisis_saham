"""Track Record — simulasi portofolio strategi composite (akuntabilitas jujur).

Simulasi PORTOFOLIO realistis (bukan quantile backtest):
  - tiap `rebalance` hari, pegang equal-weight saham ber-skor composite tertinggi
    (long_only) atau long top / short bottom (long_short, dollar-neutral);
  - tahan, ukur return; bandingkan vs benchmark equal-weight universe (long_only)
    atau vs 0/cash (long_short, market-neutral);
  - KENAKAN BIAYA: turnover x cost_bps (kedua kaki utk long_short) + borrow shorts.

Output run(): tabel `track_record` + snapshots/track_record.json (baseline long_only
mingguan = apa yg screener literal lakukan). build_panels()/simulate() dipakai juga
oleh jobs/experiment_ls.py untuk membandingkan varian.

Catatan jujur: universe S&P 500 SAAT INI -> survivorship bias, cenderung optimistis.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from config.settings import ROOT, SCORE_WEIGHTS
from config.universe import US_UNIVERSE, load_sectors
from src.backtest.metrics import max_drawdown, sharpe
from src.features.technical import indicators
from src.storage import db

WARMUP = 210
SHORT_BORROW_ANNUAL = 0.01  # 1%/th biaya pinjam saham utk kaki short


def build_panels(con):
    """Kembalikan (comp, cl_p): panel composite (date x symbol) + harga close."""
    sectors = load_sectors()
    mr, ed, cl = {}, {}, {}
    for s in US_UNIVERSE:
        df = con.execute(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE symbol = ? ORDER BY date", [s]
        ).df()
        if len(df) < WARMUP + 21:
            continue
        ind = indicators(df)
        ind.index = pd.to_datetime(ind["date"])
        mr[s], ed[s], cl[s] = ind["mr_score"], ind["event_drift_score"], ind["close"]

    mr_p, ed_p, cl_p = pd.DataFrame(mr), pd.DataFrame(ed), pd.DataFrame(cl)
    # sector-neutralize event_drift per tanggal (vektor per sektor)
    sec = {c: sectors.get(c, "?") for c in ed_p.columns}
    ed_neu = ed_p.copy()
    for secname in set(sec.values()):
        cols = [c for c in ed_p.columns if sec[c] == secname]
        if cols:
            m = ed_p[cols].mean(axis=1)
            ed_neu[cols] = (50 + ed_p[cols].sub(m, axis=0)).clip(0, 100)

    w_mr, w_ed = SCORE_WEIGHTS["mean_reversion"], SCORE_WEIGHTS["event_drift"]
    comp = (w_mr * mr_p + w_ed * ed_neu) / (w_mr + w_ed)
    return comp, cl_p


def simulate(comp, cl_p, rebalance=5, top_n=20, cost_bps=15, mode="long_only"):
    """Simulasi portofolio. mode: 'long_only' | 'long_short'. Kembalikan (metrics, curve)."""
    fwd = cl_p.shift(-rebalance) / cl_p - 1.0
    dates = comp.index.sort_values()
    rebal = dates[WARMUP::rebalance]
    borrow = SHORT_BORROW_ANNUAL * rebalance / 252

    cum_g = cum_n = cum_b = 1.0
    prev_l, prev_s = set(), set()
    rows, net_rets, bench_rets, wins = [], [], [], 0
    for d in rebal:
        sc = comp.loc[d].dropna()
        f = fwd.loc[d].dropna()
        common = sc.index.intersection(f.index)
        need = (2 * top_n if mode == "long_short" else top_n) + 5
        if len(common) < need:
            continue
        sc = sc[common]
        top = list(sc.nlargest(top_n).index)
        r_b = float(f[common].mean())

        if mode == "long_short":
            bot = list(sc.nsmallest(top_n).index)
            r_gross = float(f[top].mean()) - float(f[bot].mean())
            turn = (len(set(top) - prev_l) + len(set(bot) - prev_s)) / (2 * top_n)
            prev_l, prev_s = set(top), set(bot)
            cost = turn * (cost_bps / 10000) * 2 + borrow
            bench_ret = 0.0  # market-neutral
        else:
            r_gross = float(f[top].mean())
            turn = len(set(top) - prev_l) / top_n
            prev_l = set(top)
            cost = turn * (cost_bps / 10000) * 2
            bench_ret = r_b

        r_net = r_gross - cost
        cum_g *= 1 + r_gross
        cum_n *= 1 + r_net
        cum_b *= 1 + bench_ret
        net_rets.append(r_net)
        bench_rets.append(bench_ret)
        wins += 1 if r_net > bench_ret else 0
        rows.append({"date": str(d.date()), "strat_gross": round(cum_g, 4),
                     "strat_net": round(cum_n, 4), "bench": round(cum_b, 4)})

    n = len(rows)
    yrs = n * rebalance / 252 if n else 0
    metrics = {
        "mode": mode, "rebalance_days": rebalance, "top_n": top_n, "cost_bps": cost_bps,
        "rebalances": n, "years": round(yrs, 1),
        "strat_net_total_pct": round((cum_n - 1) * 100, 1),
        "strat_gross_total_pct": round((cum_g - 1) * 100, 1),
        "bench_total_pct": round((cum_b - 1) * 100, 1),
        "strat_net_cagr_pct": round((cum_n ** (1 / yrs) - 1) * 100, 1) if yrs > 0 else None,
        "bench_cagr_pct": round((cum_b ** (1 / yrs) - 1) * 100, 1) if yrs > 0 else None,
        "alpha_total_pct": round((cum_n - cum_b) * 100, 1),
        "hit_rate_vs_bench": round(wins / n, 3) if n else None,
        "sharpe_net": round(sharpe(np.array(net_rets), periods_per_year=252 / rebalance), 2),
        "max_drawdown_pct": round(max_drawdown([r["strat_net"] for r in rows]) * 100, 1) if rows else None,
    }
    return metrics, rows


def run() -> None:
    """Baseline realistis: long-only, rebalance BULANAN (turnover lebih rendah).

    Eksperimen (jobs/experiment_ls.py) menunjukkan bulanan jauh lebih baik dari
    mingguan (biaya turnover lebih kecil), dan long-short justru gagal total di
    rezim ini. Bulanan = cara paling masuk akal mengikuti screener.
    """
    con = db.connect(); db.init_schema(con)
    comp, cl_p = build_panels(con)
    print(f"[track] {comp.shape[1]} simbol, {comp.shape[0]} hari")
    metrics, rows = simulate(comp, cl_p, rebalance=21, top_n=20, cost_bps=15, mode="long_only")

    con.execute("CREATE TABLE IF NOT EXISTS track_record (date DATE PRIMARY KEY, "
                "strat_gross DOUBLE, strat_net DOUBLE, bench DOUBLE)")
    con.execute("DELETE FROM track_record")
    if rows:
        con.register("_tr", pd.DataFrame(rows))
        con.execute("INSERT INTO track_record BY NAME SELECT * FROM _tr")
        con.unregister("_tr")
    out = ROOT / "snapshots"; out.mkdir(exist_ok=True)
    (out / "track_record.json").write_text(json.dumps({"metrics": metrics, "curve": rows}, indent=2))
    con.close()

    m = metrics
    print(f"\n=== TRACK RECORD (baseline long-only BULANAN) · {m['years']} th ===")
    print(f"  NET {m['strat_net_total_pct']:+.1f}% (gross {m['strat_gross_total_pct']:+.1f}%) "
          f"vs benchmark {m['bench_total_pct']:+.1f}% | hit {m['hit_rate_vs_bench']} | Sharpe {m['sharpe_net']}")


if __name__ == "__main__":
    run()
