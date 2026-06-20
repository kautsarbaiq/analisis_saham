"""Entry-point batch harian US (dijalankan GitHub Actions ~04:00 WIB).

Orkestrasi end-to-end (lihat docs/01_architecture.md). Saat ini Fase 0:
hanya ingestion harga -> DuckDB. Langkah features/engines/scoring/event-study
disambung bertahap di Fase 1-2 (lihat TODO).

Harus IDEMPOTENT: aman dijalankan ulang untuk tanggal yang sama (upsert by key).
"""
from __future__ import annotations

from config.universe import US_UNIVERSE, all_symbols
from src.ingestion import prices
from src.storage import db


def run(period: str = "2y") -> None:
    """Jalankan pipeline harian US (Fase 0: harga)."""
    con = db.connect()
    db.init_schema(con)

    symbols = all_symbols() or US_UNIVERSE
    print(f"[daily_us] menarik harga {len(symbols)} simbol (period={period})...")
    df = prices.fetch(symbols, period=period)
    written = db.upsert_df(con, "prices", df, ["symbol", "date"])

    summary = con.execute(
        "SELECT count(DISTINCT symbol) AS symbols, count(*) AS rows, "
        "min(date) AS lo, max(date) AS hi FROM prices"
    ).fetchone()
    print(f"[daily_us] tertulis {written} baris. "
          f"DB sekarang: {summary[0]} simbol, {summary[1]} baris, {summary[2]}..{summary[3]}")

    # TODO(Fase 1): ingestion.fundamentals -> features.* -> engines.* -> scoring.composite
    # TODO(Fase 2): ingestion.news -> engines.event_study -> predictions
    con.close()


if __name__ == "__main__":
    run()
