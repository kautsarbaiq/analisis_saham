"""Uji efektivitas composite — jawaban terukur atas "seberapa bagus sistem ini?".

Berbeda dari track_record.py (simulasi PORTOFOLIO: berapa uangnya), job ini menguji
KUALITAS SINYAL itu sendiri, dengan metrik yang dipakai fund kuantitatif:

  1. IC (Information Coefficient) — korelasi rank composite vs return ke depan,
     dihitung CROSS-SECTIONAL PER TANGGAL lalu dirata-rata. IC 0.02-0.05 = normal
     untuk fund nyata; IC > 0.10 hampir selalu tanda bug/look-ahead.
  2. IR (Information Ratio) = mean(IC)/std(IC) — konsistensi, bukan besarnya.
  3. Peluruhan horizon — edge-nya bertahan berapa lama (h5..h63)?
  4. Kuintil per tanggal — apakah monotonik (Q0<Q1<...<Q4)?
  5. Hit-rate + Wilson CI — berapa sering top-20 mengalahkan benchmark.
  6. Rincian PER TAHUN — edge stabil, atau cuma menang di satu periode?

Semua memakai panel composite IDENTIK produksi (track_record.build_panels) dan
harga TER-ADJUST. Output -> snapshots/effectiveness.json (dibaca dashboard).

Jalankan: python -m jobs.effectiveness
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from config.settings import ROOT
from src.backtest.metrics import wilson_ci
from src.storage import db

HORIZONS = [5, 10, 21, 42, 63]
WARMUP = 210
MIN_NAMES = 50          # minimal simbol ber-skor pd suatu tanggal utk dihitung
IC_STRIDE = 5           # sampel IC tiap 5 hari bursa (kurangi overlap/autokorelasi)


def _ic_series(comp: pd.DataFrame, cl: pd.DataFrame, horizon: int) -> pd.Series:
    """IC Spearman per tanggal: rank(composite) vs rank(return ke depan).

    Non-overlap: sampel tiap `IC_STRIDE` hari; untuk t-stat dipakai jarak >= horizon
    (lihat _ic_stats) agar jendela return tidak tumpang tindih.
    """
    fwd = cl.shift(-horizon) / cl - 1.0
    dates = comp.index.sort_values()[WARMUP::IC_STRIDE]
    out = {}
    for d in dates:
        s, f = comp.loc[d], fwd.loc[d]
        both = pd.concat([s, f], axis=1, keys=["s", "f"]).dropna()
        if len(both) < MIN_NAMES:
            continue
        out[d] = both["s"].rank().corr(both["f"].rank())
    return pd.Series(out).dropna()


def _ic_stats(ic: pd.Series, horizon: int) -> dict:
    """Ringkas IC + t-stat NON-OVERLAP (ambil tiap horizon/IC_STRIDE sampel)."""
    if ic.empty:
        return {}
    step = max(1, horizon // IC_STRIDE)
    ind = ic.iloc[::step]                      # jendela tak tumpang tindih
    n = len(ind)
    t = float(ind.mean() / (ind.std(ddof=1) / np.sqrt(n))) if n > 1 and ind.std() else 0.0
    return {
        "horizon_days": horizon,
        "ic_mean": round(float(ic.mean()), 4),
        "ic_std": round(float(ic.std(ddof=1)), 4),
        "ic_ir": round(float(ic.mean() / ic.std(ddof=1)), 3) if ic.std(ddof=1) else None,
        "pct_positive": round(float((ic > 0).mean()) * 100, 1),
        "n_dates": int(len(ic)),
        "n_independent": int(n),
        "t_stat_nonoverlap": round(t, 2),
        "signifikan": bool(abs(t) >= 2.0),
    }


def _quintiles(comp: pd.DataFrame, cl: pd.DataFrame, horizon: int, q: int = 5) -> dict:
    """Rata-rata return ke depan per kuintil skor, dihitung PER TANGGAL lalu digabung."""
    fwd = cl.shift(-horizon) / cl - 1.0
    dates = comp.index.sort_values()[WARMUP::IC_STRIDE]
    buckets: dict[int, list] = {i: [] for i in range(q)}
    for d in dates:
        both = pd.concat([comp.loc[d], fwd.loc[d]], axis=1, keys=["s", "f"]).dropna()
        if len(both) < MIN_NAMES:
            continue
        try:
            lab = pd.qcut(both["s"].rank(method="first"), q, labels=False)
        except ValueError:
            continue
        for i in range(q):
            v = both.loc[lab == i, "f"]
            if len(v):
                buckets[i].append(float(v.mean()))
    means = {i: (round(float(np.mean(v)) * 100, 3) if v else None) for i, v in buckets.items()}
    vals = [means[i] for i in range(q) if means[i] is not None]
    monotonic = len(vals) == q and all(vals[i] < vals[i + 1] for i in range(q - 1))
    return {
        "horizon_days": horizon,
        "per_kuintil_pct": means,
        "spread_pct": round(vals[-1] - vals[0], 3) if len(vals) == q else None,
        "monotonik": bool(monotonic),
    }


def _per_year(comp: pd.DataFrame, cl: pd.DataFrame, horizon: int = 21, top_n: int = 20) -> list[dict]:
    """Top-N vs benchmark equal-weight, dipecah PER TAHUN (uji stabilitas rezim)."""
    fwd = cl.shift(-horizon) / cl - 1.0
    dates = comp.index.sort_values()[WARMUP::horizon]   # non-overlap
    rows: dict[int, list] = {}
    for d in dates:
        both = pd.concat([comp.loc[d], fwd.loc[d]], axis=1, keys=["s", "f"]).dropna()
        if len(both) < top_n + 5:
            continue
        top = both.nlargest(top_n, "s")["f"].mean()
        rows.setdefault(d.year, []).append((float(top), float(both["f"].mean())))
    out = []
    for y, v in sorted(rows.items()):
        strat = np.mean([x[0] for x in v]) * 100
        bench = np.mean([x[1] for x in v]) * 100
        wins = sum(1 for a, b in v if a > b)
        out.append({
            "tahun": y, "n_periode": len(v),
            "strategi_pct": round(float(strat), 2),
            "benchmark_pct": round(float(bench), 2),
            "alpha_pct": round(float(strat - bench), 2),
            "menang": wins, "unggul": bool(strat > bench),
        })
    return out


def _hit_rate(comp: pd.DataFrame, cl: pd.DataFrame, horizon: int = 21, top_n: int = 20) -> dict:
    """Frekuensi DAN besaran menang. Keduanya perlu: sinyal bisa jarang menang tapi
    tetap untung bila menangnya besar (asimetri) — dan itu mengubah cara memakainya."""
    fwd = cl.shift(-horizon) / cl - 1.0
    dates = comp.index.sort_values()[WARMUP::horizon]
    diffs = []
    for d in dates:
        both = pd.concat([comp.loc[d], fwd.loc[d]], axis=1, keys=["s", "f"]).dropna()
        if len(both) < top_n + 5:
            continue
        diffs.append(float(both.nlargest(top_n, "s")["f"].mean() - both["f"].mean()))
    n = len(diffs)
    if not n:
        return {"menang": 0, "dari": 0}
    a = np.array(diffs)
    wins = int((a > 0).sum())
    lo, hi = wilson_ci(wins, n)
    win_avg = float(a[a > 0].mean()) * 100 if (a > 0).any() else 0.0
    loss_avg = float(a[a <= 0].mean()) * 100 if (a <= 0).any() else 0.0
    return {
        "menang": wins, "dari": n,
        "hit_rate_pct": round(wins / n * 100, 1),
        "ci95_pct": [round(lo * 100, 1), round(hi * 100, 1)],
        "lebih_baik_dari_koin": bool(lo > 0.5),
        "alpha_rata2_pct": round(float(a.mean()) * 100, 2),
        "alpha_saat_menang_pct": round(win_avg, 2),
        "alpha_saat_kalah_pct": round(loss_avg, 2),
        "asimetri": round(abs(win_avg / loss_avg), 2) if loss_avg else None,
    }


def run() -> None:
    con = db.connect(); db.init_schema(con)
    from jobs.track_record import build_panels
    comp, cl = build_panels(con)          # panel IDENTIK produksi
    con.close()
    if comp.empty:
        print("[eff] composite kosong (tak ada engine tervalidasi) — uji dilewati")
        return

    print(f"[eff] panel: {comp.shape[1]} simbol x {comp.shape[0]} hari")
    ic_rows, q_rows = [], []
    for h in HORIZONS:
        ic = _ic_series(comp, cl, h)
        st = _ic_stats(ic, h)
        if st:
            ic_rows.append(st)
        q_rows.append(_quintiles(comp, cl, h))

    # Hit-rate di DUA horizon: h21 (yang dipakai rebalance produksi) dan h63
    # (tempat edge tervalidasi paling kuat) — supaya tidak menilai sinyal di
    # horizon yang bukan wilayahnya.
    hits = {f"h{h}": _hit_rate(comp, cl, horizon=h) for h in (21, 63)}
    hit = hits["h21"]
    years = _per_year(comp, cl)

    out = {
        "as_of": str(comp.index.max().date()),
        "n_simbol": int(comp.shape[1]),
        "n_hari": int(comp.shape[0]),
        "ic": ic_rows, "kuintil": q_rows, "hit_rate": hit,
        "hit_rate_per_horizon": hits, "per_tahun": years,
    }
    d = ROOT / "snapshots"; d.mkdir(exist_ok=True)
    (d / "effectiveness.json").write_text(json.dumps(out, indent=2))

    print("\n=== IC (korelasi rank skor vs return ke depan) ===")
    for r in ic_rows:
        print(f"  h{r['horizon_days']:<3} IC {r['ic_mean']:+.4f} · IR {r['ic_ir']:+.2f} · "
              f"{r['pct_positive']:.0f}% tanggal positif · t(non-overlap) {r['t_stat_nonoverlap']:+.2f} "
              f"{'SIGNIFIKAN' if r['signifikan'] else '(tidak signifikan)'}")
    print("\n=== Kuintil (return rata-rata per kelompok skor) ===")
    for r in q_rows:
        pk = r["per_kuintil_pct"]
        s = " ".join(f"Q{i}:{pk[i]:+.2f}%" if pk[i] is not None else f"Q{i}:—" for i in range(5))
        print(f"  h{r['horizon_days']:<3} {s} | spread {r['spread_pct']:+.2f}% "
              f"{'MONOTONIK ✓' if r['monotonik'] else '(tidak monotonik)'}")
    print("\n=== Hit-rate top-20 vs benchmark (non-overlap) ===")
    for hz, r in hits.items():
        print(f"  {hz:<4} {r['menang']}/{r['dari']} = {r['hit_rate_pct']}% "
              f"(CI95 {r['ci95_pct']}) — "
              f"{'lebih baik dari lempar koin' if r['lebih_baik_dari_koin'] else 'BELUM beda dari lempar koin'}")
        print(f"       alpha rata2 {r['alpha_rata2_pct']:+.2f}% · saat menang "
              f"{r['alpha_saat_menang_pct']:+.2f}% vs saat kalah {r['alpha_saat_kalah_pct']:+.2f}% "
              f"(asimetri {r['asimetri']}x)")
    print("\n=== Per tahun (h21 non-overlap, top-20 vs EW) ===")
    for y in years:
        print(f"  {y['tahun']}  strategi {y['strategi_pct']:+6.2f}%  benchmark {y['benchmark_pct']:+6.2f}%  "
              f"alpha {y['alpha_pct']:+6.2f}%  {'✓' if y['unggul'] else '✗'}  (n={y['n_periode']})")
    print("\n[eff] -> snapshots/effectiveness.json")


if __name__ == "__main__":
    run()
