"""Ingest FINRA daily short volume (5 th, universe US) ke tabel short_volume.

Audit dari kegagalan sebelumnya: inkremental PER BULAN + resumable (skip bulan yang
sudah lengkap di DB) — kill di tengah hanya kehilangan <=1 bulan, jalankan lagi utk
melanjutkan. Upsert idempotent per bulan.
"""
from __future__ import annotations

from datetime import date, timedelta

from config.universe import US_UNIVERSE
from src.ingestion.short_volume import fetch_range
from src.storage import db

START = date(2021, 6, 21)  # selaras dgn histori harga


def _month_starts(start: date, end: date):
    d = start.replace(day=1)
    while d <= end:
        yield d
        d = (d.replace(day=28) + timedelta(days=7)).replace(day=1)


def run() -> None:
    con = db.connect(); db.init_schema(con)
    uni = set(US_UNIVERSE)
    today = date.today()

    have = {r[0] for r in con.execute(
        "SELECT DISTINCT strftime(date, '%Y-%m') FROM short_volume").fetchall()}

    total = 0
    for ms in _month_starts(START, today):
        tag = ms.strftime("%Y-%m")
        me = (ms.replace(day=28) + timedelta(days=7)).replace(day=1) - timedelta(days=1)
        lo, hi = max(ms, START), min(me, today)
        # Lewati bulan yang sudah punya data & bukan bulan berjalan (bisa belum lengkap).
        if tag in have and ms.month != today.month:
            continue
        df = fetch_range(lo, hi, uni)
        if not df.empty:
            n = db.upsert_df(con, "short_volume", df, ["symbol", "date"])
            total += n
            print(f"[shortvol] {tag}: +{n} baris (kumulatif {total})")

    r = con.execute("SELECT count(*), count(DISTINCT symbol), min(date), max(date) "
                    "FROM short_volume").fetchone()
    print(f"[shortvol] SELESAI. DB: {r[0]} baris, {r[1]} simbol, {r[2]}..{r[3]}")
    con.close()


if __name__ == "__main__":
    run()
