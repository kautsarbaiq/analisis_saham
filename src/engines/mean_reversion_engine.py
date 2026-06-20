"""Mean-Reversion Engine — engine TERVALIDASI (raw walk-forward OOS).

Skor = mr_score (reversal + RSI oversold + jarak di bawah SMA20). Lolos RAW
walk-forward (positif di 3/3 periode 5 th, termasuk OOS terlama) — gerbang yang
tepat untuk screener LONG-ONLY.

DIAGNOSTIK JUJUR (dari uji sector-neutral): ~sebagian besar edge ini adalah ROTASI
SEKTOR, bukan alpha murni — saat dinetralkan per sektor, edge gabungan menyusut ~0.
Komponen `below_ma` adalah yang paling 'bersih' (paling tahan netralisasi) tapi tetap
marginal & rapuh. Jadi: edge KECIL, sebagian sektoral, MELEMAH dari waktu ke waktu.
Cocok sebagai 1 input long-only, BUKAN mesin uang.
"""
from __future__ import annotations

import pandas as pd

from src.features.technical import indicators
from src.types import EngineScore


def _r(x, nd=1):
    return round(float(x), nd) if pd.notna(x) else None


def score(symbol: str, prices_df: pd.DataFrame) -> EngineScore:
    """Skor mean-reversion (0..100, tinggi = tertekan -> kandidat pantulan)."""
    ind = indicators(prices_df)
    row = ind.iloc[-1]
    have = pd.notna(row["mr_score"])

    components = {
        "below_ma": _r(row["score_below_ma"]),      # komponen paling bersih (tahan sector-neutral)
        "oversold": _r(row["score_oversold"]),       # sebagian rotasi sektor
        "reversal": _r(row["score_rev"]),            # sebagian rotasi sektor
        "ret_1m_pct": _r(row["ret21"], 2),
        "rsi14": _r(row["rsi14"]),
    }
    sc = float(row["mr_score"]) if have else 0.0

    return EngineScore(
        symbol=symbol,
        as_of=pd.Timestamp(row["date"]).date(),
        engine="mean_reversion",
        score=round(sc, 2),
        components=components,
        sample_size=None,
        confidence="normal" if have else "low",
    )
