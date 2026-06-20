"""Smoke test: pastikan struktur & kontrak ter-import tanpa error.

Pada tahap cetak biru, test ini hanya memverifikasi bahwa modul bisa di-import dan
tipe inti tersedia. Test perilaku ditambahkan seiring implementasi tiap fase.
"""
from __future__ import annotations


def test_types_importable():
    from src.types import CompositeScore, EngineScore, Prediction

    s = EngineScore(symbol="AAPL", as_of=__import__("datetime").date(2026, 1, 1),
                    engine="technical", score=50.0)
    assert 0 <= s.score <= 100
    assert s.confidence == "normal"


def test_universe_market_detection():
    from config.universe import market_of

    assert market_of("AAPL") == "US"
    assert market_of("BBCA.JK") == "IDX"


def test_config_weights_sum_to_one():
    from config.settings import SCORE_WEIGHTS

    assert abs(sum(SCORE_WEIGHTS.values()) - 1.0) < 1e-9
