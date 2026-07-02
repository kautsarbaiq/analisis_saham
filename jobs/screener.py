"""Screener harian — Top-N skor prediktif per market, cetak + Telegram opsional.

Audit fix: dulu stub NotImplementedError yang dijadwalkan CI (gagal 100% tiap run).
Kini: baca composite TERBARU per simbol, pisah US/IDX (skala skor beda), format
ringkas + status vonis, kirim via delivery.alerts (graceful tanpa token).
Bahasa netral: "skor tertinggi", bukan "beli" (docs/07_compliance.md).
"""
from __future__ import annotations

import json

from src.delivery import alerts
from src.storage import db


def _top(con, market: str, n: int) -> list[tuple]:
    return con.execute(
        "SELECT symbol, total, breakdown, as_of FROM composite_scores "
        "WHERE total IS NOT NULL AND market = ? "
        "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1 "
        "ORDER BY total DESC LIMIT ?", [market, n],
    ).fetchall()


def _fmt_rows(rows: list[tuple]) -> str:
    out = []
    for sym, total, bd, _ in rows:
        b = json.loads(bd) if bd else {}
        parts = [f"{k[:2]}:{v:.0f}" for k, v in b.items() if v]
        out.append(f"`{sym:8}` {total:5.1f}  ({' '.join(parts)})")
    return "\n".join(out) or "(kosong)"


def run(top_n: int = 10) -> None:
    con = db.connect(); db.init_schema(con)
    us, idx = _top(con, "US", top_n), _top(con, "IDX", top_n)
    val = con.execute(
        "SELECT market, string_agg(DISTINCT engine, ', ') FROM validation "
        "WHERE validated = TRUE GROUP BY market"
    ).fetchall()
    con.close()

    asof = (us or idx)[0][3] if (us or idx) else "?"
    vtxt = " | ".join(f"{m}: {e}" for m, e in val) or "belum ada vonis"
    msg = (
        f"*PROJECT BANDAR — screener {asof}*\n"
        f"_Engine tervalidasi — {vtxt}_\n\n"
        f"*Top {len(us)} US* (blend sinyal tervalidasi US):\n{_fmt_rows(us)}\n\n"
        f"*Top {len(idx)} IDX* (sinyal tervalidasi IDX):\n{_fmt_rows(idx)}\n\n"
        f"_Skor = peringkat probabilistik ber-backtest (edge kecil), BUKAN rekomendasi "
        f"beli/jual. Edukasi & penyaring ide._"
    )
    alerts.send(msg)


if __name__ == "__main__":
    run()
