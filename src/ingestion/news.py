"""Ingestion berita (lapisan LIVE — belum di-backtest).

Sumber gratis: RSS per-ticker Yahoo Finance (real-time, tanpa API key). Dipakai untuk
overlay "berita apa & sentimennya" di dashboard, MELENGKAPI sinyal event-drift yang
sudah di-backtest. Karena RSS hanya real-time (tak ada arsip ter-tag saham gratis),
lapisan ini TIDAK bisa di-backtest -> ditandai jujur sebagai live/deskriptif.

GDELT (arsip historis) bisa ditambah nanti untuk event-study berbasis teks.
"""
from __future__ import annotations

from src.nlp.sentiment import score as sentiment_score

YF_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"


def fetch_rss(symbol: str, limit: int = 12) -> list[dict]:
    """Tarik headline terbaru untuk satu simbol + skor sentimen VADER.

    Kembalikan list {title, link, published, source, sentiment}. Aman (kembalikan []
    bila gagal/kosong) supaya dashboard tetap jalan tanpa berita.
    """
    import feedparser

    try:
        feed = feedparser.parse(YF_RSS.format(sym=symbol.upper()))
    except Exception as exc:  # noqa: BLE001
        print(f"[news] gagal {symbol}: {exc}")
        return []

    out = []
    for e in feed.entries[:limit]:
        title = getattr(e, "title", "") or ""
        out.append({
            "title": title,
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", ""),
            "source": (getattr(e, "source", {}) or {}).get("title", "Yahoo Finance"),
            "sentiment": round(sentiment_score(title), 3),
        })
    return out


def aggregate_sentiment(items: list[dict]) -> dict:
    """Ringkasan sentimen dari sekumpulan headline."""
    if not items:
        return {"count": 0, "avg": None, "pos": 0, "neg": 0, "neu": 0}
    s = [i["sentiment"] for i in items]
    return {
        "count": len(s),
        "avg": round(sum(s) / len(s), 3),
        "pos": sum(1 for x in s if x > 0.05),
        "neg": sum(1 for x in s if x < -0.05),
        "neu": sum(1 for x in s if -0.05 <= x <= 0.05),
    }
