"""Composite Score (Lapisan 6) — penggabung akhir.

Gabungkan EngineScore dari semua engine -> CompositeScore. Bobot dari
settings.SCORE_WEIGHTS (hipotesis awal, wajib dioptimasi via backtest).

Aturan confidence: engine 'low' bobotnya dikurangi (v1: x0.5, tidak dinolkan agar
total tetap informatif saat baru satu engine). Saat fundamental & lainnya masuk,
aturan ini diperketat sesuai docs/03_engines.md.
"""
from __future__ import annotations

from datetime import date

from config.settings import SCORE_WEIGHTS
from config.universe import market_of
from src.types import CompositeScore, EngineScore, Prediction


def combine(
    symbol: str,
    as_of: date,
    engine_scores: list[EngineScore],
    predictions: list[Prediction] | None = None,
    validated_engines: set[str] | None = None,
) -> CompositeScore:
    """Skor prediktif gabungan terbobot + propagasi confidence.

    `validated_engines`: himpunan engine yang LULUS backtest (tabel `validation`).
    Engine di luar himpunan ini diberi BOBOT 0 — skor deskriptifnya boleh ditampilkan
    di tempat lain, tapi tidak boleh menyetir skor prediktif (doktrin: tidak ada
    opini tanpa edge terukur). Bila `validated_engines` None, semua dianggap valid
    (mode standalone/uji).
    """
    predictions = predictions or []

    weights: dict[str, float] = {}
    for es in engine_scores:
        w = SCORE_WEIGHTS.get(es.engine, 0.0)
        if validated_engines is not None and es.engine not in validated_engines:
            w = 0.0  # belum tervalidasi -> tidak menyetir skor prediktif
        elif es.confidence == "low":
            w *= 0.5
        weights[es.engine] = w

    total_w = sum(weights.values())

    # Tidak ada engine tervalidasi -> skor prediktif BELUM TERSEDIA (jujur).
    if total_w == 0:
        return CompositeScore(
            symbol=symbol, as_of=as_of, market=market_of(symbol),
            total=None, breakdown={es.engine: round(es.score, 2) for es in engine_scores},
            predictions=predictions, confidence="low",
        )

    total = 0.0
    breakdown: dict[str, float] = {}
    for es in engine_scores:
        contrib = es.score * weights[es.engine] / total_w
        breakdown[es.engine] = round(contrib, 2)
        total += contrib

    confidence = "low" if any(es.confidence == "low" for es in engine_scores) else "normal"

    return CompositeScore(
        symbol=symbol, as_of=as_of, market=market_of(symbol),
        total=round(total, 2), breakdown=breakdown,
        predictions=predictions, confidence=confidence,
    )
