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
        "SELECT engine, horizon_days, spread, t_stat, validated, note FROM validation"
    ).fetchall()
    data = [{"engine": r[0], "horizon_days": r[1], "spread": r[2], "t_stat": r[3],
             "validated": bool(r[4]), "note": r[5]} for r in rows]
    (ROOT / "config" / "validation.json").write_text(json.dumps(data, indent=2))
    print(f"[export] config/validation.json: {len(data)} baris")


def export_snapshot(con, top: int = 50) -> None:
    asof = con.execute("SELECT max(as_of) FROM composite_scores").fetchone()[0]
    rows = con.execute(
        "SELECT symbol, total, breakdown, confidence FROM composite_scores "
        "WHERE total IS NOT NULL ORDER BY total DESC LIMIT ?", [top]
    ).fetchall()
    screener = [{"symbol": r[0], "score": round(r[1], 1),
                 "breakdown": json.loads(r[2]) if r[2] else {}, "confidence": r[3]}
                for r in rows]
    val = con.execute("SELECT DISTINCT engine FROM validation WHERE validated = TRUE").fetchall()
    snap = {"as_of": str(asof), "validated_engines": [v[0] for v in val],
            "top": screener}
    out = ROOT / "snapshots"
    out.mkdir(exist_ok=True)
    (out / "latest.json").write_text(json.dumps(snap, indent=2))
    print(f"[export] snapshots/latest.json: top {len(screener)} per {asof}")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    export_validation(con)
    export_snapshot(con)
    con.close()


if __name__ == "__main__":
    run()
