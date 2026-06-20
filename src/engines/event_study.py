"""Event Study Engine (Lapisan 5c) — FITUR PREDIKSI UNGGULAN.

Metodologi lengkap: docs/04_event_study.md. Mengubah berita -> forecast PROBABILISTIK
(P naik, CI, median CAR, N), bukan opini. Guardrail: N < MIN_SAMPLE_SIZE -> low confidence.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.features.technical import indicators
from src.types import EngineScore, Prediction


def _r(x, nd=1):
    return round(float(x), nd) if pd.notna(x) else None


def score(symbol: str, prices_df: pd.DataFrame) -> EngineScore:
    """Skor event-drift (PEAD proxy): kejutan harga pada hari ber-volume tinggi.

    Skor MENTAH per simbol; di-sector-neutralkan saat scoring (cross-sectional) karena
    edge-nya tervalidasi hanya sebagai alpha dalam-sektor (lihat backtest h63).
    """
    ind = indicators(prices_df)
    row = ind.iloc[-1]
    have = pd.notna(row["event_drift_score"])
    components = {
        "event_ret_pct": _r(row["event_ret"], 2),
        "vol_ratio": _r(row["vol_ratio"], 2),
    }
    return EngineScore(
        symbol=symbol,
        as_of=pd.Timestamp(row["date"]).date(),
        engine="event_drift",
        score=round(float(row["event_drift_score"]), 2) if have else 50.0,
        components=components,
        sample_size=None,
        confidence="normal" if have else "low",
    )


def evaluate(symbol: str, event_type: str, asof: date, regime: str) -> list[Prediction]:
    """Hasilkan forecast probabilistik per horizon untuk sebuah event berita.

    TODO(impl, Fase 2):
      1. match kejadian historis: (event_type x sektor x cap x regime).
      2. hitung Abnormal Return & CAR per kejadian (benchmark-adjusted).
      3. agregasi -> P(CAR>threshold), median, CI (scipy), N.
      4. guardrail N < MIN_SAMPLE_SIZE -> confidence='low'.
      5. bungkus jadi Prediction[] untuk FORWARD_HORIZONS.
    """
    raise NotImplementedError("Implementasi di Fase 2.")


def cumulative_abnormal_return(symbol_returns, benchmark_returns, horizon: int) -> float:
    """CAR = sum(return saham - return benchmark) selama `horizon` hari. Anti look-ahead."""
    raise NotImplementedError
