"""Skor saham IDX (Fase 3) — standalone refresh IDX.

Engine tervalidasi dibaca dari tabel `validation` WHERE market='IDX' (audit fix:
dulu hardcode). Jalankan jobs/backtest_idx.py dulu untuk mengisi vonisnya.
bandarmology proxy dihitung DESKRIPTIF (gagal backtest -> bobot 0 otomatis).
Catatan: daily_us._score_all kini juga market-aware, jadi job ini opsional
(untuk refresh IDX saja tanpa menyentuh US).
"""
from __future__ import annotations

import json

import pandas as pd

from config.universe import IDX_UNIVERSE
from jobs.daily_us import _validated_engines
from src.engines import bandarmology_engine, mean_reversion_engine
from src.scoring import composite
from src.storage import db


def run() -> None:
    con = db.connect(); db.init_schema(con)
    validated = _validated_engines(con, "IDX")
    es_rows, cs_rows = [], []
    for sym in IDX_UNIVERSE:
        pdf = con.execute(db.ADJ_PRICES_SQL, [sym]).df()
        if len(pdf) < 220:
            continue
        el = [mean_reversion_engine.score(sym, pdf), bandarmology_engine.score(sym, pdf)]
        for es in el:
            es_rows.append({
                "symbol": es.symbol, "as_of": es.as_of, "engine": es.engine,
                "score": es.score, "sample_size": es.sample_size,
                "confidence": es.confidence, "components": json.dumps(es.components),
            })
        cs = composite.combine(sym, el[0].as_of, el, validated_engines=validated)
        cs_rows.append({
            "symbol": cs.symbol, "as_of": cs.as_of, "market": cs.market,
            "total": cs.total, "breakdown": json.dumps(cs.breakdown), "confidence": cs.confidence,
        })

    if es_rows:
        db.upsert_df(con, "engine_scores", pd.DataFrame(es_rows), ["symbol", "as_of", "engine"])
    if cs_rows:
        cs_df = pd.DataFrame(cs_rows)
        cs_df["total"] = pd.to_numeric(cs_df["total"], errors="coerce")
        db.upsert_df(con, "composite_scores", cs_df, ["symbol", "as_of"])
    print(f"[score_idx] {len(cs_rows)} saham IDX ter-skor (tervalidasi IDX: {validated or '-'})")
    print("Top 6 IDX:", con.execute(
        "SELECT symbol, round(total,1) FROM composite_scores WHERE market='IDX' "
        "AND total IS NOT NULL ORDER BY total DESC LIMIT 6").fetchall())
    con.close()


if __name__ == "__main__":
    run()
