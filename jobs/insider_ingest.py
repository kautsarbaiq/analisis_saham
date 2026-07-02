"""Ingest insider buys (SEC bulk Form 345) ke DuckDB. Jalan sekali / kuartalan.

Audit fix: (1) rentang kuartal DINAMIS sampai kuartal berjalan (dulu hardcode
2026Q1 — akan basi selamanya); kuartal yang belum dirilis SEC otomatis ter-skip
(fetch gagal -> df kosong). (2) DELETE+INSERT dibungkus TRANSAKSI — crash di
tengah tidak meninggalkan tabel kosong.
"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd

from src.ingestion.insider import fetch_quarter, quarters_range
from src.storage import db

START = (2022, 1)


def run() -> None:
    con = db.connect(); db.init_schema(con)

    today = date.today()
    end_q = (today.month - 1) // 3 + 1
    frames = []
    for y, q in quarters_range(START[0], START[1], today.year, end_q):
        df = fetch_quarter(y, q)
        if len(df):
            frames.append(df)
        time.sleep(0.5)

    if not frames:
        print("[insider] tidak ada data terunduh — tabel lama dibiarkan utuh")
        con.close(); return

    allb = pd.concat(frames, ignore_index=True)
    con.register("_ib", allb[["accession", "symbol", "trans_date", "filing_date",
                              "shares", "price", "value"]])
    try:
        con.execute("BEGIN")
        con.execute("DELETE FROM insider_buys")
        con.execute("INSERT INTO insider_buys BY NAME SELECT * FROM _ib")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("_ib")

    r = con.execute("SELECT count(*), count(DISTINCT symbol), min(filing_date), max(filing_date) "
                    "FROM insider_buys").fetchone()
    print(f"\n[insider] TOTAL {r[0]} pembelian | {r[1]} emiten | {r[2]}..{r[3]}")
    con.close()


if __name__ == "__main__":
    run()
