"""Event Study Engine (Lapisan 5c) — FITUR PREDIKSI UNGGULAN.

Metodologi lengkap: docs/04_event_study.md. Mengubah berita -> forecast PROBABILISTIK
(P naik, CI, median CAR, N), bukan opini. Guardrail: N < MIN_SAMPLE_SIZE -> low confidence.
"""
from __future__ import annotations

from datetime import date

from src.types import Prediction


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
