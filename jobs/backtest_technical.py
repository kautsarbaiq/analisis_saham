"""Backtest engine teknikal: ukur apakah skornya punya edge, lalu persist vonis.

Menjalankan quantile test untuk beberapa horizon, menentukan validated = (spread > 0
dan t_stat > 2), dan menyimpan hasilnya ke tabel `validation`. composite.py memakai
tabel ini untuk memutuskan apakah engine teknikal boleh diberi bobot.

CATATAN KEJUJURAN (ditampilkan tiap run):
  - Universe kecil (15 mega-cap) & observasi tumpang-tindih -> N efektif jauh lebih
    kecil dari N mentah; t-stat cenderung terlalu yakin.
  - Survivorship: hanya saham yang masih hidup -> hasil cenderung optimistis.
  Jadi vonis ini indikatif, bukan kata akhir.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from config.universe import US_UNIVERSE
from src.backtest.engine import build_panel, quantile_test
from src.storage import db

HORIZONS = [5, 21]
T_THRESHOLD = 2.0  # |t| minimal agar dianggap signifikan (indikatif)


def run() -> None:
    con = db.connect()
    db.init_schema(con)

    prices = {}
    for s in US_UNIVERSE:
        df = con.execute(
            "SELECT date, close FROM prices WHERE symbol = ? ORDER BY date", [s]
        ).df()
        if len(df) >= 220:
            prices[s] = df

    rows = []
    print(f"\n=== BACKTEST ENGINE TEKNIKAL · {len(prices)} simbol ===")
    print("CATATAN: universe kecil + observasi tumpang-tindih + survivorship -> "
          "vonis indikatif, cenderung optimistis.\n")

    for h in HORIZONS:
        panel = build_panel(prices, horizon=h)
        res = quantile_test(panel, n_quantiles=5)
        validated = bool(res["spread"] > 0 and abs(res["t_stat"]) > T_THRESHOLD and res["t_stat"] > 0)
        note = (
            "edge positif terukur" if validated
            else f"TIDAK ada edge positif (spread {res['spread']:+.2f}%, "
                 f"t={res['t_stat']}) — kemungkinan rezim mean-reversion"
        )
        print(f"horizon {h:>2}h | top={res['top_mean']:+.2f}% bottom={res['bottom_mean']:+.2f}% "
              f"spread={res['spread']:+.2f}% t={res['t_stat']:+.2f} | "
              f"{'VALID ✓' if validated else 'TOLAK ✗'} — {note}")
        rows.append({
            "engine": "technical", "horizon_days": h, "market": "US", "as_of": date.today(),
            "n_obs": res["n_obs"], "top_mean": res["top_mean"],
            "bottom_mean": res["bottom_mean"], "spread": res["spread"],
            "t_stat": res["t_stat"], "validated": validated, "note": note,
        })

    db.upsert_df(con, "validation", pd.DataFrame(rows), ["engine", "horizon_days", "market"])
    con.close()
    print("\nVonis tersimpan di tabel `validation`. composite.py menolak engine "
          "yang belum VALID (bobot 0).")


if __name__ == "__main__":
    run()
