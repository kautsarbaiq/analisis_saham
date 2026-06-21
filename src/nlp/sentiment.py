"""Skor sentimen finansial berita.

Baseline: VADER (gratis, instan, tanpa model berat). Upgrade nanti: FinBERT (lebih
akurat untuk teks finansial). Output: skor [-1, +1] (compound VADER).
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()


def score(text: str, model: str = "vader") -> float:
    """Skor sentimen [-1..+1] dari sepotong teks (mis. judul berita)."""
    if not text:
        return 0.0
    return float(_analyzer().polarity_scores(text)["compound"])
