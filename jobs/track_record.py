"""Track Record — simulasi portofolio strategi composite (akuntabilitas jujur).

Bukan backtest faktor (quantile), tapi simulasi PORTOFOLIO realistis:
  - tiap REBALANCE hari, pegang equal-weight TOP_N saham ber-skor composite tertinggi
    (mean_reversion + event_drift sector-neutral, point-in-time);
  - tahan REBALANCE hari, ukur return; bandingkan vs benchmark equal-weight universe;
  - KENAKAN BIAYA TRANSAKSI (turnover x COST_BPS) — krn mean-reversion turnover tinggi
    dan biaya bisa memakan edge yang kecil. Tampilkan gross & net apa adanya.

Output: tabel `track_record` + snapshots/track_record.json (utk dashboard).
Catatan jujur: ini simulasi pada universe S&P 500 SAAT INI (survivorship bias) ->
cenderung optimistis. Live track record (forward) tumbuh dari snapshot harian.
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

REBALANCE = 5      # hari perdagangan (mingguan)
TOP_N = 20
COST_BPS = 15      # biaya per sisi per nama yang berganti (basis poin)
WARMUP = 210       # lewati awal (butuh SMA200)


def run() -> None:
    con = db.connect(); db.init_schema(con)
    sectors = load_sectors()

    mr, ed, cl = {}, {}, {}
    for s in US_UNIVERSE:
        df = con.execute(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE symbol = ? ORDER BY date", [s]
        ).df()
        if len(df) < WARMUP + REBALANCE:
            continue
        ind = indicators(df)
        ind.index = pd.to_datetime(ind["date"])
        mr[s], ed[s], cl[s] = ind["mr_score"], ind["event_drift_score"], ind["close"]

    mr_p, ed_p, cl_p = pd.DataFrame(mr), pd.DataFrame(ed), pd.DataFrame(cl)
    print(f"[track] {mr_p.shape[1]} simbol, {mr_p.shape[0]} hari")

    # Sector-neutralize event_drift per tanggal (vektor per sektor).
    sec = {c: sectors.get(c, "?") for c in ed_p.columns}
    ed_neu = ed_p.copy()
    for secname in set(sec.values()):
        cols = [c for c in ed_p.columns if sec[c] == secname]
        if not cols:
            continue
        m = ed_p[cols].mean(axis=1)
        ed_neu[cols] = (50 + ed_p[cols].sub(m, axis=0)).clip(0, 100)

    w_mr, w_ed = SCORE_WEIGHTS["mean_reversion"], SCORE_WEIGHTS["event_drift"]
    comp = (w_mr * mr_p + w_ed * ed_neu) / (w_mr + w_ed)

    fwd = cl_p.shift(-REBALANCE) / cl_p - 1.0
    dates = comp.index.sort_values()
    rebal = dates[WARMUP::REBALANCE]

    cum_g = cum_n = cum_b = 1.0
    prev: set[str] = set()
    rows, strat_rets, bench_rets, wins = [], [], [], 0
    for d in rebal:
        sc = comp.loc[d].dropna()
        f = fwd.loc[d].dropna()
        common = sc.index.intersection(f.index)
        if len(common) < TOP_N + 5:
            continue
        sc = sc[common]
        top = list(sc.nlargest(TOP_N).index)
        r_s = float(f[top].mean())
        r_b = float(f[common].mean())
        turn = len(set(top) - prev) / TOP_N
        cost = turn * (COST_BPS / 10000) * 2  # beli + jual sisi yang berganti
        prev = set(top)

        cum_g *= 1 + r_s
        cum_n *= 1 + r_s - cost
        cum_b *= 1 + r_b
        strat_rets.append(r_s - cost)
        bench_rets.append(r_b)
        wins += 1 if (r_s - cost) > r_b else 0
        rows.append({"date": str(d.date()), "strat_gross": round(cum_g, 4),
                     "strat_net": round(cum_n, 4), "bench": round(cum_b, 4)})

    n = len(rows)
    yrs = n * REBALANCE / 252
    sr, br = np.array(strat_rets), np.array(bench_rets)
    metrics = {
        "rebalances": n, "years": round(yrs, 1), "top_n": TOP_N,
        "rebalance_days": REBALANCE, "cost_bps": COST_BPS,
        "strat_net_total_pct": round((cum_n - 1) * 100, 1),
        "strat_gross_total_pct": round((cum_g - 1) * 100, 1),
        "bench_total_pct": round((cum_b - 1) * 100, 1),
        "strat_net_cagr_pct": round((cum_n ** (1 / yrs) - 1) * 100, 1) if yrs else None,
        "bench_cagr_pct": round((cum_b ** (1 / yrs) - 1) * 100, 1) if yrs else None,
        "alpha_total_pct": round((cum_n - cum_b) * 100, 1),
        "hit_rate_vs_bench": round(wins / n, 3) if n else None,
        "sharpe_net": round(sharpe(sr, periods_per_year=252 / REBALANCE), 2),
        "max_drawdown_pct": round(max_drawdown([r["strat_net"] for r in rows]) * 100, 1),
        "avg_turnover": round(float(np.mean([1.0])), 2),  # placeholder; turnover tinggi utk MR
    }

    # Persist
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

    print(f"\n=== TRACK RECORD · {yrs:.1f} th · rebalance {REBALANCE}h · top {TOP_N} · biaya {COST_BPS}bps ===")
    print(f"  Strategi NET total : {metrics['strat_net_total_pct']:+.1f}%  (gross {metrics['strat_gross_total_pct']:+.1f}%)")
    print(f"  Benchmark (EW univ): {metrics['bench_total_pct']:+.1f}%")
    print(f"  ALPHA net vs bench : {metrics['alpha_total_pct']:+.1f}%")
    print(f"  CAGR net {metrics['strat_net_cagr_pct']}% vs bench {metrics['bench_cagr_pct']}%")
    print(f"  Hit-rate vs bench  : {metrics['hit_rate_vs_bench']*100:.1f}% | Sharpe net {metrics['sharpe_net']} | maxDD {metrics['max_drawdown_pct']}%")


if __name__ == "__main__":
    run()
