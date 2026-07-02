"""Unit test gerbang composite: hanya engine tervalidasi yang menyetir skor."""
from __future__ import annotations

from datetime import date

from src.scoring.composite import combine
from src.types import EngineScore


def _es(engine: str, score: float, conf: str = "normal") -> EngineScore:
    return EngineScore(symbol="TEST", as_of=date(2026, 1, 2), engine=engine,
                       score=score, components={}, confidence=conf)


def test_unvalidated_engine_gets_zero_weight():
    scores = [_es("event_drift", 80.0), _es("technical", 10.0)]
    cs = combine("TEST", date(2026, 1, 2), scores, validated_engines={"event_drift"})
    assert cs.total == 80.0                       # technical (10) tidak menyeret turun
    assert cs.breakdown["technical"] == 0.0


def test_no_validated_engines_means_no_score():
    cs = combine("TEST", date(2026, 1, 2), [_es("technical", 99.0)],
                 validated_engines=set())
    assert cs.total is None                       # jujur: tak ada skor prediktif
    assert cs.confidence == "low"


def test_low_conf_zero_weight_engine_does_not_force_low():
    # Audit fix: engine deskriptif ber-bobot-0 (low) tak boleh menular ke composite.
    scores = [_es("event_drift", 70.0), _es("bandarmology", 50.0, conf="low")]
    cs = combine("TEST", date(2026, 1, 2), scores, validated_engines={"event_drift"})
    assert cs.confidence == "normal"


def test_low_conf_weighted_engine_halved_and_marks_low():
    scores = [_es("event_drift", 100.0), _es("insider", 0.0, conf="low")]
    cs = combine("TEST", date(2026, 1, 2), scores,
                 validated_engines={"event_drift", "insider"})
    # bobot insider dipangkas 50% tapi tetap >0 -> confidence low & total di antara
    assert cs.confidence == "low"
    assert 0 < cs.total < 100
