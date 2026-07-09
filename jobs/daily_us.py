"""Entry-point batch harian (GitHub Actions ~04:00 WIB / launchd lokal).

Pipeline nyata (lihat docs/01_architecture.md):
  1. Harga bulk universe US (S&P 500) + IDX (LQ45) -> tabel prices (upsert).
  2. Opsional: fundamental SEC EDGAR untuk simbol US -> tabel fundamentals.
  3. _score_all (market-aware, sinyal dari harga TER-ADJUST via db.ADJ_PRICES_SQL):
     technical / mean_reversion / event_drift / insider (US-only) / fundamental;
     event_drift di-sector-neutralkan cross-sectional per market; composite
     hanya atas engine tervalidasi untuk market ybs (tabel `validation`,
     fallback config/validation.json) -> engine_scores + composite_scores.

Harus IDEMPOTENT: aman dijalankan ulang untuk tanggal yang sama (upsert by key).
"""
import json

import pandas as pd

from config.settings import ROOT
from config.universe import US_UNIVERSE, all_symbols, load_sectors, market_of
from src.engines import (
    event_study, fundamental_engine, insider_engine, mean_reversion_engine,
    shortvol_engine, technical_engine,
)
from src.ingestion import fundamentals, prices
from src.scoring import composite
from src.storage import db


def _validated_engines(con, market: str = "US") -> set[str]:
    """Engine yang lulus backtest UNTUK MARKET tsb (audit fix: dulu market-blind —
    vonis US ikut menyetir IDX padahal mis. event_drift kontrarian di IDX).
    Dari tabel `validation`; bila kosong (runner CI fresh) fallback ke
    config/validation.json (statis, juga ber-market)."""
    try:
        rows = con.execute(
            "SELECT DISTINCT engine FROM validation WHERE validated = TRUE AND market = ?",
            [market],
        ).fetchall()
        eng = {r[0] for r in rows}
        if eng:
            return eng
    except Exception:
        pass
    f = ROOT / "config" / "validation.json"
    if f.exists():
        return {x["engine"] for x in json.loads(f.read_text())
                if x.get("validated") and x.get("market", "US") == market}
    return set()


def _score_all(con, symbols: list[str]) -> None:
    """Hitung engine_scores + composite_scores (dua-pass utk sector-relative).

    Pass 1: skor per-simbol semua engine (event_drift masih MENTAH).
    Antara: event_drift di-sector-neutralkan cross-sectional (edge-nya tervalidasi
            hanya sebagai alpha dalam-sektor).
    Pass 2: composite atas engine tervalidasi.
    """
    validated_by_market = {
        "US": _validated_engines(con, "US"),
        "IDX": _validated_engines(con, "IDX"),
    }
    sectors = load_sectors()

    # Pembelian insider 90 hari terakhir (data bulk Form 345). Audit fix: deteksi
    # STALENESS — data bulk kuartalan bisa tertinggal jauh dari hari ini; bila
    # anchor (max filing_date) lebih tua dari 45 hari, sinyal insider ditandai
    # low-confidence (bobotnya otomatis dipangkas di composite).
    ins_counts: dict[str, int] = {}
    ins_stale = True
    try:
        maxf = con.execute("SELECT max(filing_date) FROM insider_buys").fetchone()[0]
        if maxf:
            from datetime import date as _date
            ins_stale = (_date.today() - maxf).days > 45
            rows = con.execute(
                "SELECT symbol, count(*) FROM insider_buys "
                "WHERE filing_date > ? - INTERVAL 90 DAY GROUP BY symbol", [maxf]
            ).fetchall()
            ins_counts = {r[0]: int(r[1]) for r in rows}
    except Exception:
        ins_counts = {}

    # Short volume FINRA per simbol US + staleness (data harian, bisa tertinggal).
    sv_by_sym: dict[str, pd.DataFrame] = {}
    sv_stale = True
    try:
        sv = con.execute("SELECT symbol, date, short_vol, total_vol FROM short_volume").df()
        if not sv.empty:
            sv["date"] = pd.to_datetime(sv["date"])
            from datetime import date as _d2
            sv_stale = (_d2.today() - sv["date"].max().date()).days > 7
            sv_by_sym = {s: g for s, g in sv.groupby("symbol")}
    except Exception:
        sv_by_sym = {}

    per_symbol: dict[str, dict] = {}
    for sym in symbols:
        pdf = con.execute(db.ADJ_PRICES_SQL, [sym]).df()
        if len(pdf) < 220:
            continue

        el = [technical_engine.score(sym, pdf),
              mean_reversion_engine.score(sym, pdf),
              event_study.score(sym, pdf)]
        if market_of(sym) == "US":  # insider & short-volume hanya utk emiten AS
            el.append(insider_engine.score(sym, ins_counts.get(sym, 0), el[0].as_of,
                                           stale=ins_stale))
            el.append(shortvol_engine.score(sym, sv_by_sym.get(sym), el[0].as_of,
                                            stale=sv_stale))
        fdf = con.execute(
            "SELECT period, metric, value FROM fundamentals WHERE symbol = ?", [sym]
        ).df()
        if len(fdf):
            el.append(fundamental_engine.score(sym, fdf, float(pdf["close"].iloc[-1])))
        per_symbol[sym] = {"el": el, "as_of": el[0].as_of}

    # --- Sector-neutralize event_drift & shortvol_level (demean per market:sektor) ---
    # Audit fix: grup demean MARKET-AWARE. Kedua engine tervalidasi dlm bentuk
    # sector-neutral, jadi diproduksi dgn cara yang sama (identik gerbang backtest).
    def _group(sym: str) -> str:
        return f"{market_of(sym)}:" + sectors.get(sym, "?")

    for eng in ("event_drift", "shortvol_level"):
        sec_vals: dict[str, list] = {}
        for sym, d in per_symbol.items():
            es = next((e for e in d["el"] if e.engine == eng), None)
            if es is not None:
                sec_vals.setdefault(_group(sym), []).append(es.score)
        sec_mean = {s: sum(v) / len(v) for s, v in sec_vals.items()}
        for sym, d in per_symbol.items():
            sec = _group(sym)
            for e in d["el"]:
                if e.engine == eng and sec in sec_mean:
                    e.score = round(max(0.0, min(100.0, 50 + (e.score - sec_mean[sec]))), 2)

    es_rows, cs_rows = [], []
    for sym, d in per_symbol.items():
        for es in d["el"]:
            es_rows.append({
                "symbol": es.symbol, "as_of": es.as_of, "engine": es.engine,
                "score": es.score, "sample_size": es.sample_size,
                "confidence": es.confidence, "components": json.dumps(es.components),
            })
        cs = composite.combine(sym, d["as_of"], d["el"],
                               validated_engines=validated_by_market[market_of(sym)])
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
          f"(tervalidasi US: {validated_by_market['US'] or '-'} | "
          f"IDX: {validated_by_market['IDX'] or '-'} | "
          f"insider_stale={ins_stale} shortvol_stale={sv_stale})")


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
