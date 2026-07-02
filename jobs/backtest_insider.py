"""Backtest sinyal insider-buying (SEC Form 4 'P') — independen dari harga/fundamental.

Event-study cross-sectional: tiap tanggal rebalance, bandingkan return ke depan
saham yang punya >=K pembelian insider dalam LOOKBACK hari (pakai FILING_DATE -> anti
look-ahead) vs rata-rata universe (abnormal return). Walk-forward per periode.

VALIDATED bila abnormal > 0 & konsisten di semua periode termasuk OOS terlama.
Uji K=1 (ada pembelian) dan K=2 (cluster buy, sinyal lebih kuat).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from src.storage import db

HORIZONS = [21, 63]
LOOKBACK = 90          # hari kalender jendela "pembelian baru"
WARMUP = 210
# Audit fix: langkah sampling = HORIZON (jendela NON-OVERLAP). Dulu langkah 5 hari
# dgn horizon 21/63 -> observasi tumpang-tindih menginflasi t-stat (autokorelasi).
# Non-overlap = t jujur (obs independen), meski N lebih kecil.


def _periods(dates):
    n = len(dates)
    return [(dates[0], dates[n // 3]), (dates[n // 3], dates[2 * n // 3]), (dates[2 * n // 3], dates[-1])]


def run() -> None:
    con = db.connect(); db.init_schema(con)
    ib = con.execute("SELECT symbol, filing_date FROM insider_buys").df()
    if ib.empty:
        print("Tabel insider_buys kosong — jalankan jobs.insider_ingest dulu."); con.close(); return
    ib["filing_date"] = pd.to_datetime(ib["filing_date"])
    px = con.execute(
        "SELECT symbol, date, adj_close AS close FROM prices ORDER BY symbol, date"
    ).df()
    con.close()
    px["date"] = pd.to_datetime(px["date"])
    close = px.pivot_table(index="date", columns="symbol", values="close").sort_index()

    buys = defaultdict(list)
    for r in ib.itertuples():
        buys[r.symbol].append(r.filing_date)
    for s in buys:
        buys[s].sort()
    print(f"[insider-bt] {len(ib)} pembelian, {len(buys)} emiten unik")

    for K in (1, 2):
        print(f"\n===== SINYAL: >={K} pembelian insider dalam {LOOKBACK} hari =====")
        for H in HORIZONS:
            fwd = close.shift(-H) / close - 1.0
            dates = close.index
            rebal = dates[WARMUP::H]  # non-overlap: langkah = horizon
            recs = []
            for d in rebal:
                f = fwd.loc[d].dropna()
                if len(f) < 50:
                    continue
                lo = d - pd.Timedelta(days=LOOKBACK)
                bset = [s for s in f.index if s in buys
                        and sum(1 for fd in buys[s] if lo < fd <= d) >= K]
                if len(bset) < 3:
                    continue
                recs.append({"date": d, "abn": float(f[bset].mean() - f.mean()), "n": len(bset)})
            if not recs:
                print(f"  H{H}: data tak cukup"); continue
            p = pd.DataFrame(recs)
            abn = p["abn"].to_numpy()
            t = float(abn.mean() / (abn.std(ddof=1) / np.sqrt(len(abn)))) if abn.std() > 0 else float("nan")
            fold_means = []
            for lo, hi in _periods(p["date"].tolist()):
                sub = p[(p["date"] >= lo) & (p["date"] <= hi)]["abn"]
                fold_means.append(round(float(sub.mean()) * 100, 2))
            valid = abn.mean() > 0 and t > 2 and all(x > 0 for x in fold_means)
            print(f"  H{H:>2}: abnormal/periode rata2 {abn.mean()*100:+.2f}% (t {t:+.2f}) "
                  f"| per-periode {fold_means} | avg n={p['n'].mean():.0f} "
                  f"| {'VALID ✓' if valid else 'tolak'}")
            # Persist verdict kanonik engine 'insider' (sinyal K>=1, horizon 21h).
            if K == 1 and H == 21:
                con2 = db.connect(); db.init_schema(con2)
                note = (f"insider open-market buy (>=1, 90d) abnormal {abn.mean()*100:+.2f}%/21d, "
                        f"per-periode {fold_means} (t {t:+.2f}); INDEPENDEN dari harga/fundamental; "
                        f"edge kecil & melemah; equal-weight (outlier TPL ter-redam 1/n)")
                db.upsert_df(con2, "validation", pd.DataFrame([{
                    "engine": "insider", "horizon_days": 21, "market": "US",
                    "as_of": date.today(),
                    "n_obs": int(len(p)), "top_mean": round(abn.mean() * 100, 3),
                    "bottom_mean": 0.0, "spread": round(abn.mean() * 100, 3),
                    "t_stat": round(t, 3), "validated": bool(valid), "note": note,
                }]), ["engine", "horizon_days", "market"])
                con2.close()


if __name__ == "__main__":
    run()
