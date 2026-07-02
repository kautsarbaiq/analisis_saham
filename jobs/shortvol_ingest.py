"""Ingest FINRA daily short volume (5 th, universe US) ke tabel short_volume."""
from __future__ import annotations

from datetime import date

from config.universe import US_UNIVERSE
from src.ingestion.short_volume import fetch_range
from src.storage import db

START = date(2021, 6, 21)  # selaras dgn histori harga


def run() -> None:
    con = db.connect(); db.init_schema(con)
    df = fetch_range(START, date.today(), set(US_UNIVERSE))
    if df.empty:
        print("[shortvol] tidak ada data"); con.close(); return
    n = db.upsert_df(con, "short_volume", df, ["symbol", "date"])
    r = con.execute("SELECT count(*), count(DISTINCT symbol), min(date), max(date) "
                    "FROM short_volume").fetchone()
    print(f"[shortvol] upsert {n} | DB: {r[0]} baris, {r[1]} simbol, {r[2]}..{r[3]}")
    con.close()


if __name__ == "__main__":
    run()
