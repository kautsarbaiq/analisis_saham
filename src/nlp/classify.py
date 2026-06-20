"""Klasifikasi tipe event dari berita (input event-study).

Strategi hemat: aturan/keyword dulu (gratis, cepat) -> LLM (Groq free) hanya untuk
kasus ambigu. Output WAJIB satu dari taksonomi tertutup agar bisa di-match historis.
"""
from __future__ import annotations

EVENT_TYPES = [
    "earnings_beat", "earnings_miss", "guidance_up", "guidance_down",
    "mna", "analyst_upgrade", "analyst_downgrade", "regulatory",
    "macro", "management_change", "buyback", "dividend", "lawsuit", "other",
]


def classify(title: str, body: str | None = None) -> dict:
    """Kembalikan {event_type, surprise_magnitude?, confidence}.

    TODO(impl, Fase 2): rules -> fallback Groq. Pastikan event_type ∈ EVENT_TYPES.
    """
    raise NotImplementedError("Implementasi di Fase 2.")
