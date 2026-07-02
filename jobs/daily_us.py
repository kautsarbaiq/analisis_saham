"""Entry-point batch harian US (dijalankan GitHub Actions ~04:00 WIB).

Orkestrasi end-to-end (lihat docs/01_architecture.md). Saat ini Fase 0:
hanya ingestion harga -> DuckDB. Langkah features/engines/scoring/event-study
disambung bertahap di Fase 1-2 (lihat TODO).

Harus IDEMPOTENT: aman dijalankan ulang untuk tanggal yang sama (upsert by key).
"""
import json

import pandas as pd

from config.settings import ROOT
from config.universe import US_UNIVERSE, all_symbols, load_sectors
from src.engines import (
    event_study, fundamental_engine, insider_engine, mean_reversion_engine, technical_engine,
)
from src.ingestion import fundamentals, prices
from src.scoring import composite
from src.storage import db


def _validated_engines(con) -> set[str]:
    """Engine yang lulus backtest. Dari tabel `validation`; bila kosong (mis. runner
    GitHub Actions yang DB-nya fresh), fallback ke config/validation.json (statis)."""
    try:
        rows = con.execute(
            "SELECT DISTINCT engine FROM validation WHERE validated = TRUE"
        ).fetchall()
        eng = {r[0] for r in rows}
        if eng:
            return eng
    except Exception:
        pass
    f = ROOT / "config" / "validation.json"
    if f.exists():
        return {x["engine"] for x in json.loads(f.read_text()) if x.get("validated")}
    return set()


def _score_all(con, symbols: list[str]) -> None:
    """Hitung engine_scores + composite_scores (dua-pass utk sector-relative).

    Pass 1: skor per-simbol semua engine (event_drift masih MENTAH).
    Antara: event_drift di-sector-neutralkan cross-sectional (edge-nya tervalidasi
            hanya sebagai alpha dalam-sektor).
    Pass 2: composite atas engine tervalidasi.
    """
    validated = _validated_engines(con)
    sectors = load_sectors()

    # Pembelian insider 90 hari terakhir (dari data bulk Form 345 yang tersedia).
    ins_counts: dict[str, int] = {}
    try:
        maxf = con.execute("SELECT max(filing_date) FROM insider_buys").fetchone()[0]
        if maxf:
            rows = con.execute(
                "SELECT symbol, count(*) FROM insider_buys "
                "WHERE filing_date > ? - INTERVAL 90 DAY GROUP BY symbol", [maxf]
            ).fetchall()
            ins_counts = {r[0]: int(r[1]) for r in rows}
    except Exception:
        ins_counts = {}

    per_symbol: dict[str, dict] = {}
    for sym in symbols:
        pdf = con.execute(db.ADJ_PRICES_SQL, [sym]).df()
        if len(pdf) < 220:
            continue

        el = [technical_engine.score(sym, pdf),
              mean_reversion_engine.score(sym, pdf),
              event_study.score(sym, pdf)]
        el.append(insider_engine.score(sym, ins_counts.get(sym, 0), el[0].as_of))
        fdf = con.execute(
            "SELECT period, metric, value FROM fundamentals WHERE symbol = ?", [sym]
        ).df()
        if len(fdf):
            el.append(fundamental_engine.score(sym, fdf, float(pdf["close"].iloc[-1])))
        per_symbol[sym] = {"el": el, "as_of": el[0].as_of}

    # --- Sector-neutralize event_drift (demean per sektor, rescale 0..100) ---
    sec_vals: dict[str, list] = {}
    for sym, d in per_symbol.items():
        raw = next(e.score for e in d["el"] if e.engine == "event_drift")
        sec_vals.setdefault(sectors.get(sym, "?"), []).append(raw)
    sec_mean = {s: sum(v) / len(v) for s, v in sec_vals.items()}
    for sym, d in per_symbol.items():
        sec = sectors.get(sym, "?")
        for e in d["el"]:
            if e.engine == "event_drift":
                e.score = round(max(0.0, min(100.0, 50 + (e.score - sec_mean[sec]))), 2)

    es_rows, cs_rows = [], []
    for sym, d in per_symbol.items():
        for es in d["el"]:
            es_rows.append({
                "symbol": es.symbol, "as_of": es.as_of, "engine": es.engine,
                "score": es.score, "sample_size": es.sample_size,
                "confidence": es.confidence, "components": json.dumps(es.components),
            })
        cs = composite.combine(sym, d["as_of"], d["el"], validated_engines=validated)
        cs_rows.append({
            "symbol": cs.symbol, "as_of": cs.as_of, "market": cs.market,
            "total": cs.total, "breakdown": json.dumps(cs.breakdown),
            "confidence": cs.confidence,
        })

    if es_rows:
        db.upsert_df(con, "engine_scores", pd.DataFrame(es_rows), ["symbol", "as_of", "engine"])
    if cs_rows:
        cs_df = pd.DataFrame(cs_rows)
        cs_df["total"] = pd.to_numeric(cs_df["total"], errors="coerce")
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
