"""Entry-point batch harian US (dijalankan GitHub Actions ~04:00 WIB).

Orkestrasi end-to-end (lihat docs/01_architecture.md). Saat ini Fase 0:
hanya ingestion harga -> DuckDB. Langkah features/engines/scoring/event-study
disambung bertahap di Fase 1-2 (lihat TODO).

Harus IDEMPOTENT: aman dijalankan ulang untuk tanggal yang sama (upsert by key).
"""
import json

import pandas as pd

from config.universe import US_UNIVERSE, all_symbols
from src.engines import fundamental_engine, mean_reversion_engine, technical_engine
from src.ingestion import fundamentals, prices
from src.scoring import composite
from src.storage import db


def _validated_engines(con) -> set[str]:
    """Engine yang lulus backtest (tabel `validation`). Kosong jika backtest belum jalan."""
    try:
        rows = con.execute(
            "SELECT DISTINCT engine FROM validation WHERE validated = TRUE"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()


def _score_all(con, symbols: list[str]) -> None:
    """Hitung engine_scores (teknikal) + composite_scores untuk tiap simbol."""
    validated = _validated_engines(con)
    es_rows, cs_rows = [], []

    for sym in symbols:
        pdf = con.execute(
            "SELECT date, open, high, low, close, adj_close, volume "
            "FROM prices WHERE symbol = ? ORDER BY date", [sym]
        ).df()
        if len(pdf) < 30:
            continue

        engine_list = []

        te = technical_engine.score(sym, pdf)
        engine_list.append(te)

        engine_list.append(mean_reversion_engine.score(sym, pdf))

        fdf = con.execute(
            "SELECT period, metric, value FROM fundamentals WHERE symbol = ?", [sym]
        ).df()
        if len(fdf):
            fe = fundamental_engine.score(sym, fdf, float(pdf["close"].iloc[-1]))
            engine_list.append(fe)

        for es in engine_list:
            es_rows.append({
                "symbol": es.symbol, "as_of": es.as_of, "engine": es.engine,
                "score": es.score, "sample_size": es.sample_size,
                "confidence": es.confidence, "components": json.dumps(es.components),
            })

        cs = composite.combine(sym, te.as_of, engine_list, validated_engines=validated)
        cs_rows.append({
            "symbol": cs.symbol, "as_of": cs.as_of, "market": cs.market,
            "total": cs.total, "breakdown": json.dumps(cs.breakdown),
            "confidence": cs.confidence,
        })

    if es_rows:
        db.upsert_df(con, "engine_scores", pd.DataFrame(es_rows), ["symbol", "as_of", "engine"])
    if cs_rows:
        cs_df = pd.DataFrame(cs_rows)
        cs_df["total"] = pd.to_numeric(cs_df["total"], errors="coerce")  # None -> NaN -> NULL
        db.upsert_df(con, "composite_scores", cs_df, ["symbol", "as_of"])
    print(f"[daily_us] skor: {len(es_rows)} engine_scores, {len(cs_rows)} composite_scores "
          f"(engine tervalidasi: {validated or 'belum ada'})")


def run(period: str = "2y", with_fundamentals: bool = True) -> None:
    """Jalankan pipeline harian US (harga + fundamental + skor teknikal & fundamental)."""
    con = db.connect()
    db.init_schema(con)

    symbols = all_symbols() or US_UNIVERSE
    print(f"[daily_us] menarik harga {len(symbols)} simbol (period={period})...")
    df = prices.fetch_bulk(symbols, period=period)
    written = db.upsert_df(con, "prices", df, ["symbol", "date"])

    summary = con.execute(
        "SELECT count(DISTINCT symbol) AS symbols, count(*) AS rows, "
        "min(date) AS lo, max(date) AS hi FROM prices"
    ).fetchone()
    print(f"[daily_us] tertulis {written} baris. "
          f"DB sekarang: {summary[0]} simbol, {summary[1]} baris, {summary[2]}..{summary[3]}")

    if with_fundamentals:
        us = [s for s in symbols if not s.upper().endswith(".JK")]
        print(f"[daily_us] menarik fundamental SEC EDGAR {len(us)} simbol...")
        fdf = fundamentals.fetch(us)
        if len(fdf):
            db.upsert_df(con, "fundamentals", fdf, ["symbol", "period", "metric"])
            print(f"[daily_us] fundamental: {len(fdf)} titik metrik tersimpan")

    _score_all(con, symbols)

    # TODO(Fase 1): ingestion.fundamentals -> features.fundamental -> fundamental_engine
    # TODO(Fase 2): ingestion.news -> engines.event_study -> predictions
    con.close()


if __name__ == "__main__":
    run()
