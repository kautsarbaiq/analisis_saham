"""Ingestion berita (GDELT + RSS + NewsAPI free).

Untuk event-study, GDELT adalah aset utama: arsip event global GRATIS & historis,
ideal untuk mencari "N kejadian serupa di masa lalu".

Tanggung jawab:
  - tarik headline + metadata (JANGAN simpan full text artikel berhak cipta; simpan link)
  - dedup via hash(url+title)
  - set `available_at` = timestamp publikasi (anti look-ahead di event-study)
  - serahkan klasifikasi event ke nlp/classify.py dan sentimen ke nlp/sentiment.py
"""
from __future__ import annotations


def fetch_rss(feeds: list[str]):
    """Tarik headline real-time dari daftar RSS (feedparser). Untuk alert & sentimen harian."""
    raise NotImplementedError("Implementasi di Fase 2.")


def fetch_gdelt(query: str, start, end):
    """Query arsip GDELT untuk event historis (basis matching event-study)."""
    raise NotImplementedError("Implementasi di Fase 2.")


def dedup_id(url: str, title: str) -> str:
    """Hash stabil untuk dedup berita lintas sumber."""
    raise NotImplementedError
