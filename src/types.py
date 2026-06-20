"""Tipe data bersama lintas-lapisan (kontrak antar modul).

Menjaga semua engine bicara "bahasa" yang sama sehingga Lapisan 6 (composite) dan
halaman Track Record bisa menggabung & mengaudit output secara seragam.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Confidence = Literal["normal", "low"]
Market = Literal["US", "IDX"]


@dataclass
class EngineScore:
    """Output standar setiap engine analitis (Lapisan 5).

    score   : 0..100 (lebih tinggi = lebih bullish).
    components: breakdown terukur pembentuk skor (audit trail).
    sample_size: N bila skor berbasis historis; None bila tidak relevan.
    confidence : "low" jika sample_size < MIN_SAMPLE_SIZE.
    """
    symbol: str
    as_of: date
    engine: str
    score: float
    components: dict = field(default_factory=dict)
    sample_size: int | None = None
    confidence: Confidence = "normal"


@dataclass
class Prediction:
    """Forecast probabilistik yang disimpan untuk diaudit Track Record."""
    symbol: str
    as_of: date
    horizon_days: int
    prob_up: float            # P(naik > threshold)
    ci_low: float
    ci_high: float
    median_return: float
    sample_size: int
    rationale: str            # alasan terukur (tipe event, dsb)
    confidence: Confidence
    # diisi belakangan oleh jobs/track_record.py:
    realized_return: float | None = None
    was_correct: bool | None = None


@dataclass
class CompositeScore:
    """Skor gabungan akhir (Lapisan 6) yang ditampilkan ke user."""
    symbol: str
    as_of: date
    market: Market
    total: float                       # 0..100
    breakdown: dict[str, float]        # kontribusi tiap engine
    predictions: list[Prediction] = field(default_factory=list)
    confidence: Confidence = "normal"
