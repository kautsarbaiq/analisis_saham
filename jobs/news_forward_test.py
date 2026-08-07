"""Uji-maju lapisan berita — apakah sentimen/kategori headline PUNYA edge terukur?

Kenapa "uji-maju" (forward test), bukan backtest biasa: tidak ada arsip berita
ter-tag saham yang gratis, jadi arsip dibangun dari nol oleh jobs/news_digest.py
(tabel `news`, ber-timestamp `available_at`). Job ini mengevaluasi arsip itu
begitu sampelnya cukup.

Metodologi (rigor sama dgn engine lain):
  - return TER-ADJUST (db.ADJ_PRICES_SQL);
  - ANTI LOOK-AHEAD: berita available_at hari-D dievaluasi dgn return dari CLOSE
    hari perdagangan berikutnya (>= D) ke depan — headline sore tidak boleh
    diklaim memprediksi penutupan hari yang sama;
  - return diukur ABNORMAL (relatif rata-rata universe hari itu), supaya bukan
    sekadar ikut arah pasar;
  - vonis butuh N >= MIN_N dan |t| >= 2.

Sebelum sampel cukup, job ini JUJUR bilang "belum bisa divonis" — bukan
menampilkan angka setengah matang.

Jalankan: python -m jobs.news_forward_test
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from config.settings import ROOT
from src.storage import db

HORIZONS = [1, 5]
MIN_N = 200          # minimal pasangan (berita, return) sebelum boleh divonis
MIN_PER_GROUP = 30   # minimal per kategori


def _panel(con) -> pd.DataFrame:
    """Gabungkan arsip berita dgn return abnormal ke depan."""
    news = con.execute(
        "SELECT id, symbol, title, available_at, event_type, sentiment FROM news "
        "WHERE symbol IS NOT NULL AND sentiment IS NOT NULL"
    ).df()
    if news.empty:
        return pd.DataFrame()
    news["date"] = pd.to_datetime(news["available_at"]).dt.tz_localize(None).dt.normalize()

    syms = sorted(news["symbol"].unique())
    frames = []
    for s in syms:
        px = con.execute(db.ADJ_PRICES_SQL, [s]).df()
        if len(px) < 30:
            continue
        px["date"] = pd.to_datetime(px["date"])
        px = px[["date", "close"]].copy()
        px["symbol"] = s
        for h in HORIZONS:
            px[f"fwd{h}"] = (px["close"].shift(-h) / px["close"] - 1.0) * 100
        frames.append(px)
    if not frames:
        return pd.DataFrame()
    prices = pd.concat(frames, ignore_index=True)

    # Return abnormal = return saham - rata-rata universe pada tanggal yang sama.
    for h in HORIZONS:
        prices[f"ab{h}"] = prices[f"fwd{h}"] - prices.groupby("date")[f"fwd{h}"].transform("mean")

    # ANTI LOOK-AHEAD: pasangkan berita ke hari perdagangan PERTAMA >= tanggal berita.
    # merge_asof menuntut KEDUA sisi terurut menurut kunci `on` (date), bukan per grup.
    prices = prices.sort_values("date")
    news = news.sort_values("date")
    out = pd.merge_asof(
        news, prices, left_on="date", right_on="date", by="symbol",
        direction="forward", tolerance=pd.Timedelta(days=5),
    )
    keep = ["symbol", "title", "date", "event_type", "sentiment"] + [f"ab{h}" for h in HORIZONS]
    return out[keep].dropna(subset=[f"ab{h}" for h in HORIZONS], how="all")


def _t(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return 0.0
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def run() -> None:
    con = db.connect(); db.init_schema(con)
    p = _panel(con)
    con.close()

    con2 = db.connect()
    n_arsip = con2.execute("SELECT count(*) FROM news WHERE symbol IS NOT NULL").fetchone()[0]
    con2.close()

    total = len(p)
    hasil = {"n_arsip": int(n_arsip), "n_terpasang": int(total), "min_n": MIN_N,
             "cukup": bool(total >= MIN_N), "horizon": {}, "per_kategori": {}}

    if total < MIN_N:
        print(f"[news-test] arsip {n_arsip} berita; {total} sudah bisa dipasangkan dgn "
              f"return (sisanya LEBIH BARU dari data harga terakhir — normal, bukan bug).\n"
              f"            Butuh >= {MIN_N} pasangan untuk vonis. Jalankan "
              f"jobs.news_digest tiap hari agar arsip menumpuk.")
    else:
        for h in HORIZONS:
            col = f"ab{h}"
            d = p.dropna(subset=[col])
            pos = d[d["sentiment"] > 0.05][col].to_numpy()
            neg = d[d["sentiment"] < -0.05][col].to_numpy()
            spread = (pos.mean() - neg.mean()) if len(pos) and len(neg) else None
            hasil["horizon"][f"h{h}"] = {
                "n_positif": int(len(pos)), "n_negatif": int(len(neg)),
                "ab_positif_pct": round(float(pos.mean()), 3) if len(pos) else None,
                "ab_negatif_pct": round(float(neg.mean()), 3) if len(neg) else None,
                "spread_pct": round(float(spread), 3) if spread is not None else None,
                "t_positif": round(_t(pos), 2), "t_negatif": round(_t(neg), 2),
                "tervalidasi": bool(spread is not None and spread > 0
                                    and abs(_t(pos)) >= 2 and len(pos) >= MIN_PER_GROUP),
            }
            for kat, g in d.groupby("event_type"):
                if len(g) < MIN_PER_GROUP:
                    continue
                v = g[col].to_numpy()
                hasil["per_kategori"].setdefault(f"h{h}", {})[kat] = {
                    "n": int(len(v)), "ab_pct": round(float(v.mean()), 3), "t": round(_t(v), 2)}

        print(f"[news-test] {total} berita ter-arsip\n")
        for hz, r in hasil["horizon"].items():
            print(f"  {hz}: positif {r['ab_positif_pct']}% (n={r['n_positif']}, t={r['t_positif']}) | "
                  f"negatif {r['ab_negatif_pct']}% (n={r['n_negatif']}, t={r['t_negatif']}) | "
                  f"spread {r['spread_pct']}% -> "
                  f"{'TERVALIDASI' if r['tervalidasi'] else 'belum tervalidasi'}")

    d = ROOT / "snapshots"; d.mkdir(exist_ok=True)
    (d / "news_validation.json").write_text(json.dumps(hasil, indent=2))
    print(f"\n[news-test] -> snapshots/news_validation.json")


if __name__ == "__main__":
    run()
