"""Ingest insider buys (SEC bulk Form 345) ke DuckDB. Jalan sekali / kuartalan."""
from __future__ import annotations

import time

from src.ingestion.insider import fetch_quarter, quarters_range
from src.storage import db


def run() -> None:
    con = db.connect(); db.init_schema(con)
    con.execute("CREATE TABLE IF NOT EXISTS insider_buys ("
                "accession VARCHAR, symbol VARCHAR, trans_date DATE, filing_date DATE, "
                "shares DOUBLE, price DOUBLE, value DOUBLE)")
    con.execute("DELETE FROM insider_buys")

    total = 0
    for y, q in quarters_range(2022, 1, 2026, 1):
        df = fetch_quarter(y, q)
        if len(df):
            con.register("_ib", df)
            con.execute("INSERT INTO insider_buys BY NAME SELECT "
                        "accession, symbol, trans_date, filing_date, shares, price, value FROM _ib")
            con.unregister("_ib")
            total += len(df)
        time.sleep(0.5)

    r = con.execute("SELECT count(*), count(DISTINCT symbol), min(filing_date), max(filing_date) "
                    "FROM insider_buys").fetchone()
    print(f"\n[insider] TOTAL {total} pembelian | {r[1]} emiten | {r[2]}..{r[3]}")
    con.close()


if __name__ == "__main__":
    run()
