"""Export snapshot untuk otomatisasi (GitHub Actions / hosting).

Menghasilkan:
  - config/validation.json : vonis backtest per engine (STATIS — backtest sesekali,
    bukan harian). Dipakai daily pipeline utk tahu engine mana tervalidasi tanpa
    harus rebuild backtest 5 th (penting agar GitHub Actions bisa scoring di runner
    ephemeral).
  - snapshots/latest.json   : screener prediktif terbaru (di-commit balik oleh CI;
    jadi rekam jejak harian + bisa disajikan dashboard hosted nanti).
"""
from __future__ import annotations

import json
from pathlib import Path

from config.settings import ROOT
from src.storage import db


def export_validation(con) -> None:
    rows = con.execute(
        "SELECT engine, horizon_days, market, spread, t_stat, validated, note FROM validation"
    ).fetchall()
    # Audit fix (anti-clobber CI): runner fresh punya tabel validation KOSONG —
    # jangan timpa config/validation.json (sumber vonis) dengan [].
    if not rows:
        print("[export] validation kosong — config/validation.json TIDAK ditimpa")
        return
    data = [{"engine": r[0], "horizon_days": r[1], "market": r[2], "spread": r[3],
             "t_stat": r[4], "validated": bool(r[5]), "note": r[6]} for r in rows]
    (ROOT / "config" / "validation.json").write_text(json.dumps(data, indent=2))
    print(f"[export] config/validation.json: {len(data)} baris")


def export_snapshot(con, top: int = 50) -> None:
    # Audit fix: (1) hanya skor TERBARU per simbol (dulu mencampur as_of basi lintas
    # tanggal); (2) US & IDX dipisah (skala composite beda: blend multi-engine vs
    # engine tunggal — tidak apple-to-apple dalam satu ranking); (3) simbol yang
    # skornya tertinggal >7 hari dari batch terbaru DIBUANG — itu opini rezim lama
    # (mis. simbol berhenti ter-skor), bukan skor "terkini".
    rows = con.execute(
        "SELECT symbol, total, breakdown, confidence, market, as_of FROM composite_scores "
        "WHERE total IS NOT NULL "
        "AND as_of >= (SELECT max(as_of) FROM composite_scores) - INTERVAL 7 DAY "
        "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1 "
        "ORDER BY total DESC"
    ).fetchall()

    def _fmt(r):
        return {"symbol": r[0], "score": round(r[1], 1),
                "breakdown": json.loads(r[2]) if r[2] else {},
                "confidence": r[3], "as_of": str(r[5])}

    top_us = [_fmt(r) for r in rows if r[4] == "US"][:top]
    top_idx = [_fmt(r) for r in rows if r[4] == "IDX"][:top]

    val = con.execute(
        "SELECT market, engine FROM validation WHERE validated = TRUE"
    ).fetchall()
    validated_by_market: dict[str, list] = {}
    for mkt, eng in val:
        validated_by_market.setdefault(mkt, []).append(eng)

    asof = con.execute("SELECT max(as_of) FROM composite_scores").fetchone()[0]
    snap = {"as_of": str(asof), "validated_engines": validated_by_market,
            "top_us": top_us, "top_idx": top_idx}
    out = ROOT / "snapshots"
    out.mkdir(exist_ok=True)
    (out / "latest.json").write_text(json.dumps(snap, indent=2))
    print(f"[export] snapshots/latest.json: US {len(top_us)} + IDX {len(top_idx)} per {asof}")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    export_validation(con)
    export_snapshot(con)
    con.close()


if __name__ == "__main__":
    run()
