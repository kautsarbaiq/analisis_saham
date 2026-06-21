"""Skor sentimen finansial berita.

Dua mode:
  - 'vader'   : cepat, ringan, umum (baseline).
  - 'finbert' : ProsusAI/finbert — model khusus teks FINANSIAL, jauh lebih akurat
                untuk konteks bursa (mis. "beat estimates", "downgrade"). Model
                ~440MB diunduh sekali; inferensi lokal & gratis.

Output: skor [-1, +1] (negatif..positif).
"""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _vader():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    return SentimentIntensityAnalyzer()


@lru_cache(maxsize=1)
def _finbert():
    from transformers import pipeline
    return pipeline("sentiment-analysis", model="ProsusAI/finbert", truncation=True)


def score(text: str, model: str = "finbert") -> float:
    """Skor sentimen [-1..+1] dari teks. Default FinBERT (finansial)."""
    if not text:
        return 0.0
    if model == "finbert":
        try:
            r = _finbert()(text[:512])[0]
            lab, conf = r["label"].lower(), float(r["score"])
            signed = conf if lab == "positive" else -conf if lab == "negative" else 0.0
            return round(signed, 3)
        except Exception:  # noqa: BLE001 — fallback ke VADER bila model gagal
            pass
    return round(float(_vader().polarity_scores(text)["compound"]), 3)
