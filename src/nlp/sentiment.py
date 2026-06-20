"""Skor sentimen finansial berita.

Baseline: VADER (gratis, instan). Upgrade: FinBERT (lebih akurat untuk teks finansial,
lokal & gratis tapi lebih berat). Output: skor [-1, +1].
"""
from __future__ import annotations


def score(text: str, model: str = "vader") -> float:
    """Skor sentimen [-1..+1]. model ∈ {'vader','finbert'}.

    TODO(impl, Fase 2): VADER dulu; FinBERT via transformers saat akurasi diperlukan.
    """
    raise NotImplementedError("Implementasi di Fase 2.")
