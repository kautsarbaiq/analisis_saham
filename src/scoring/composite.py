"""Composite Score (Lapisan 6) — penggabung akhir.

Gabungkan EngineScore dari semua engine + forecast event-study -> CompositeScore yang
ditampilkan ke user. Bobot dari settings.SCORE_WEIGHTS adalah HIPOTESIS AWAL yang WAJIB
dioptimasi via backtest — bukan ditebak permanen.

Aturan: engine dengan confidence 'low' atau yang belum tervalidasi backtest -> bobot
efektifnya diturunkan/0, dan total confidence ikut turun.
"""
from __future__ import annotations

from datetime import date

from src.types import CompositeScore, EngineScore, Prediction


def combine(
    symbol: str,
    asof: date,
    engine_scores: list[EngineScore],
    predictions: list[Prediction],
) -> CompositeScore:
    """Hitung skor gabungan terbobot + propagasi confidence.

    TODO(impl, Fase 1):
      - ambil bobot dari SCORE_WEIGHTS, nolkan engine yang 'low'/belum tervalidasi.
      - renormalisasi bobot yang tersisa.
      - total = sum(weight_i * score_i); breakdown simpan kontribusi tiap engine.
      - confidence = 'low' bila mayoritas bobot berasal dari engine low-confidence.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
