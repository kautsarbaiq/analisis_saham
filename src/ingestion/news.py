"""Ingestion berita (lapisan LIVE — status validasi jujur, lihat catatan di bawah).

Sumber gratis tanpa API key:
  - RSS per-ticker Yahoo Finance (berita spesifik emiten),
  - RSS pasar/makro (Yahoo top-stories, CNBC, Reuters biz) untuk berita yang
    memengaruhi banyak saham sekaligus.

STATUS VALIDASI (non-negosiasi, jangan dikaburkan di UI):
  - Klasifikasi kategori (earnings/M&A/regulasi/...) = HEURISTIK kata kunci,
    transparan tapi BELUM di-backtest.
  - Sentimen (FinBERT) = deskriptif, BELUM di-backtest sebagai sinyal.
  - Yang SUDAH tervalidasi hanyalah sinyal harga (event_drift, shortvol_level);
    berita dipakai sebagai KONTEKS "apa yang sedang terjadi", bukan prediktor.
  - `persist()` menyimpan headline+sentimen ber-timestamp supaya lapisan ini
    BISA di-backtest nanti (jobs/news_forward_test.py) — arsip dibangun dari
    sekarang karena tak ada arsip berita ter-tag saham yang gratis.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

import pandas as pd

from src.nlp.sentiment import score as sentiment_score

YF_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"

# Feed pasar/makro — berita yang memengaruhi banyak emiten sekaligus.
MARKET_FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "CNBC Economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
}

# Kategori berita + kata kunci. HEURISTIK TRANSPARAN (bukan model terlatih):
# urutan penting — kategori pertama yang cocok dipakai. Bobot `w` = dugaan
# a-priori "seberapa sering kategori ini menggerakkan harga", DIKUNCI sebelum
# uji, dan hanya dipakai untuk MENGURUTKAN tampilan — bukan untuk memprediksi.
EVENT_RULES: list[tuple[str, float, tuple[str, ...]]] = [
    ("bangkrut/gagal bayar", 1.00, ("bankrupt", "chapter 11", "default", "insolven", "delist")),
    ("merger/akuisisi",      0.95, ("merger", "acquisition", "acquire", "takeover", "buyout", "to buy")),
    ("laba/guidance",        0.90, ("earnings", "quarterly result", "guidance", "outlook", "profit",
                                    "revenue", "eps", "beats", "misses", "forecast")),
    ("regulasi/hukum",       0.80, ("lawsuit", "sue", "settlement", "antitrust", "investigation",
                                    "probe", "fine", "sanction", "regulator", "sec charges")),
    ("persetujuan produk",   0.75, ("fda", "approval", "approved", "trial result", "patent")),
    ("rating analis",        0.65, ("upgrade", "downgrade", "price target", "initiated coverage",
                                    "overweight", "underweight")),
    ("manajemen",            0.60, ("ceo", "cfo", "resign", "steps down", "appoint", "chief executive")),
    ("aksi korporasi",       0.60, ("dividend", "buyback", "repurchase", "split", "spin-off", "offering")),
    ("makro/suku bunga",     0.55, ("fed", "inflation", "cpi", "rate cut", "rate hike", "tariff",
                                    "jobs report", "gdp", "recession", "bank indonesia", "the fed")),
    ("suplai/operasional",   0.50, ("recall", "outage", "strike", "supply chain", "shortage",
                                    "production halt", "layoff")),
]


def classify(title: str) -> tuple[str, float]:
    """Kategori + bobot a-priori dari kata kunci. ('umum', 0.3) bila tak cocok."""
    t = (title or "").lower()
    for name, w, keys in EVENT_RULES:
        if any(k in t for k in keys):
            return name, w
    return "umum", 0.30


def _uid(url: str, title: str) -> str:
    return hashlib.sha1(f"{url}|{title}".encode()).hexdigest()[:16]


def _parse_time(entry) -> datetime:
    """Timestamp publikasi (UTC). Fallback: sekarang — jangan pernah mengarang masa lalu."""
    for attr in ("published_parsed", "updated_parsed"):
        v = getattr(entry, attr, None)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return datetime.now(timezone.utc)


def _entries(url: str, limit: int):
    import feedparser
    try:
        return feedparser.parse(url).entries[:limit]
    except Exception as exc:  # noqa: BLE001 — sumber eksternal, jangan gugurkan dashboard
        print(f"[news] gagal feed {url}: {exc}")
        return []


def _item(entry, symbol: str | None, default_source: str) -> dict:
    title = getattr(entry, "title", "") or ""
    link = getattr(entry, "link", "") or ""
    cat, w = classify(title)
    src = (getattr(entry, "source", {}) or {}).get("title") or default_source
    ts = _parse_time(entry)
    return {
        "id": _uid(link, title),
        "symbol": symbol,
        "title": title,
        "url": link,
        "source": src,
        "available_at": ts,
        "published": ts.strftime("%Y-%m-%d %H:%M UTC"),
        "event_type": cat,
        "event_weight": w,
        "sentiment": round(sentiment_score(title), 3),
    }


def fetch_rss(symbol: str, limit: int = 12) -> list[dict]:
    """Headline terbaru untuk satu simbol + sentimen + kategori (heuristik)."""
    sym = symbol.upper()
    # RSS Yahoo per-ticker hanya utk emiten AS; simbol .JK tidak punya feed ini.
    return [_item(e, sym, "Yahoo Finance")
            for e in _entries(YF_RSS.format(sym=sym), limit)]


def fetch_market(limit_per_feed: int = 12) -> list[dict]:
    """Berita pasar/makro (tanpa simbol) — memengaruhi banyak emiten sekaligus."""
    seen, out = set(), []
    for name, url in MARKET_FEEDS.items():
        for e in _entries(url, limit_per_feed):
            it = _item(e, None, name)
            if it["id"] in seen or not it["title"]:
                continue
            seen.add(it["id"])
            out.append(it)
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


def persist(con, items: list[dict]) -> int:
    """Simpan headline ke tabel `news` (idempotent by id) — membangun ARSIP agar
    lapisan berita bisa di-backtest nanti. Kolom sesuai schema.sql."""
    if not items:
        return 0
    from src.storage import db
    df = pd.DataFrame([{
        "id": i["id"], "symbol": i["symbol"], "title": i["title"], "url": i["url"],
        "source": i["source"], "available_at": i["available_at"],
        "event_type": i["event_type"], "sentiment": i["sentiment"],
    } for i in items])
    df = df.drop_duplicates(subset=["id"])
    return db.upsert_df(con, "news", df, ["id"])


_NAMES: dict[str, str] | None = None


def _names() -> dict[str, str]:
    global _NAMES
    if _NAMES is None:
        from config.universe import load_names
        _NAMES = load_names()
    return _NAMES


def mentions(title: str, symbol: str) -> bool:
    """Apakah headline menyebut TICKER atau NAMA emiten secara eksplisit?

    Word-boundary agar tidak asal cocok ('AMD' tak boleh cocok di tengah kata).
    Nama dicocokkan dari kata pertama yang cukup khas (mis. 'BlackRock' dari
    "BlackRock", 'Meta' dari "Meta Platforms") — supaya "PayPal to Stripe..."
    tetap terhubung ke PYPL walau tickernya tak disebut.
    """
    t = title or ""
    base = symbol.upper().replace(".JK", "")
    if len(base) >= 2 and re.search(rf"\b{re.escape(base)}\b", t, re.IGNORECASE):
        return True
    name = _names().get(symbol.upper(), "")
    if not name:
        return False
    head = name.split()[0]
    # kata generik ("First", "American", ...) terlalu sering muncul -> butuh nama penuh
    needle = name if len(head) < 5 else head
    return re.search(rf"\b{re.escape(needle)}\b", t, re.IGNORECASE) is not None
