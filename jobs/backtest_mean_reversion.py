"""Backtest engine MEAN-REVERSION — dengan validasi out-of-sample lintas waktu.

Hipotesis (dari temuan momentum kontrarian): saham 'oversold' cenderung memantul.
Sinyal mr_score dibangun A-PRIORI (reversal + RSI oversold + jarak di bawah SMA20),
konstruksinya berbeda dari tech_score.

Disiplin anti-overfitting:
  - Histori 5 tahun dibagi 3 PERIODE. Periode TERLAMA (2021-2022) = out-of-sample
    sejati terhadap pengamatan kontrarian (yang berasal dari 2024-2026).
  - Validated HANYA jika: pooled signifikan (t>2) DAN spread positif di KETIGA
    periode termasuk yang terlama. Mencegah edge yang cuma artefak satu rezim.
  - Catatan: t-stat pooled menggelembung karena observasi tumpang-tindih; konsistensi
    antar-periode adalah bukti yang lebih bermakna daripada t mentah.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import US_UNIVERSE
from src.backtest.engine import build_panel, quantile_test
from src.storage import db

HORIZONS = [5, 10]


def _folds(panel: pd.DataFrame, n: int = 3) -> list[tuple]:
    dts = pd.to_datetime(panel["date"]).sort_values().unique()
    cuts = [dts[0]] + [dts[len(dts) * k // n] for k in range(1, n)] + [dts[-1]]
    return [(cuts[k], cuts[k + 1]) for k in range(n)]


def run() -> None:
    con = db.connect(); db.init_schema(con)

    prices = {}
    for s in US_UNIVERSE:
        df = con.execute(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE symbol = ? ORDER BY date", [s]
        ).df()
        if len(df) >= 260:
            prices[s] = df
    print(f"=== BACKTEST MEAN-REVERSION · {len(prices)} simbol ===")

    rows = []
    for h in HORIZONS:
        panel = build_panel(prices, horizon=h, score_col="mr_score")
        panel["date"] = pd.to_datetime(panel["date"])
        res = quantile_test(panel, n_quantiles=5)
        print(f"\nhorizon {h}h · {res['n_obs']} obs")
        for b in res["buckets"]:
            print(f"  Q{b['q']} mean_fwd={b['mean_fwd']:+.2f}% win={b['win_rate']*100:4.1f}% n={b['n']}")
        print(f"  POOLED spread(top-bottom)={res['spread']:+.2f}%  t={res['t_stat']}")

        fold_spreads = []
        for k, (lo, hi) in enumerate(_folds(panel)):
            sub = panel[(panel["date"] >= lo) & (panel["date"] <= hi)]
            fr = quantile_test(sub, n_quantiles=5)
            fold_spreads.append(fr["spread"])
            tag = " (OOS terlama)" if k == 0 else ""
            print(f"  periode {k+1} [{pd.Timestamp(lo).date()}..{pd.Timestamp(hi).date()}]"
                  f" spread={fr['spread']:+.2f}% t={fr['t_stat']}{tag}")

        early_ok = fold_spreads[0] > 0
        all_pos = all(s > 0 for s in fold_spreads)
        validated = bool(res["spread"] > 0 and res["t_stat"] > 2 and early_ok and all_pos)
        if validated:
            note = (f"edge KONSISTEN: pooled +{res['spread']:.2f}% (t {res['t_stat']}), "
                    f"positif di 3/3 periode termasuk OOS terlama")
        else:
            note = (f"belum lolos: pooled {res['spread']:+.2f}% (t {res['t_stat']}); "
                    f"per-periode {[round(s,2) for s in fold_spreads]} "
                    f"(butuh positif di ketiga, termasuk OOS terlama)")
        print(f"  >> VONIS h{h}: {'VALID ✓' if validated else 'TOLAK ✗'} — {note}")

        rows.append({
            "engine": "mean_reversion", "horizon_days": h, "as_of": date.today(),
            "n_obs": int(res["n_obs"]), "top_mean": res["top_mean"],
            "bottom_mean": res["bottom_mean"], "spread": res["spread"],
            "t_stat": res["t_stat"], "validated": validated, "note": note,
        })

    db.upsert_df(con, "validation", pd.DataFrame(rows), ["engine", "horizon_days"])
    con.close()


if __name__ == "__main__":
    run()
