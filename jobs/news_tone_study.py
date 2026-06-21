"""Studi metodologi: apakah TONE berita GDELT memprediksi return? (sampel kecil).

PENTING — keterbatasan jujur: GDELT DOC API rate-limited + jendela ~12 bln, jadi ini
hanya SAMPEL KECIL & periode pendek -> TIDAK setara rigor faktor harga (5 th x 500
saham, walk-forward + sector-neutral). Hasilnya INDIKATIF, untuk memutuskan apakah
layak investasi BigQuery demi versi penuh. Bukan vonis `validation`.

Mengukur Information Coefficient (korelasi Spearman) antara tone (dan perubahan tone)
hari-T dengan return ke depan H hari.
"""
from __future__ import annotations

import time

import pandas as pd

from src.ingestion.gdelt import tone_timeline
from src.storage import db

HORIZON = 5
SAMPLE = [
    ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"),
    ("AMZN", "Amazon"), ("JPM", "JPMorgan"), ("XOM", "Exxon"),
    ("INTU", "Intuit"), ("WMT", "Walmart"),
]


def run() -> None:
    con = db.connect(); db.init_schema(con)
    frames = []
    for sym, name in SAMPLE:
        rows = tone_timeline(sym, name, timespan="12m")
        if not rows:
            print(f"[news_tone] {sym}: GDELT kosong/terblok")
            continue
        g = pd.DataFrame(rows)
        g["date"] = pd.to_datetime(g["date"], format="%Y%m%d")
        g = g.dropna(subset=["tone"])

        px = con.execute("SELECT date, close FROM prices WHERE symbol=? ORDER BY date", [sym]).df()
        px["date"] = pd.to_datetime(px["date"])
        px["fwd"] = (px["close"].shift(-HORIZON) / px["close"] - 1.0) * 100

        m = pd.merge_asof(g.sort_values("date"), px.sort_values("date"), on="date")
        m["tone_chg"] = m["tone"].diff()
        m["symbol"] = sym
        frames.append(m.dropna(subset=["fwd", "tone"]))
        print(f"[news_tone] {sym}: {len(rows)} hari tone, {len(frames[-1])} selaras")
        time.sleep(3)

    con.close()
    if not frames:
        print("Tidak ada data GDELT (kemungkinan rate-limited)."); return

    panel = pd.concat(frames, ignore_index=True)
    ic_tone = panel["tone"].corr(panel["fwd"], method="spearman")
    ic_chg = panel["tone_chg"].corr(panel["fwd"], method="spearman")
    print(f"\n=== STUDI TONE BERITA · {panel['symbol'].nunique()} saham · "
          f"{len(panel)} obs · horizon {HORIZON}h ===")
    print(f"  IC(tone -> fwd return)        = {ic_tone:+.3f}")
    print(f"  IC(perubahan tone -> fwd ret) = {ic_chg:+.3f}")
    print("  (|IC|>0.03-0.05 dianggap berarti di kuant; ingat sampel kecil & "
          "periode pendek -> indikatif, BUKAN tervalidasi)")


if __name__ == "__main__":
    run()
