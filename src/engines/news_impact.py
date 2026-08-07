"""Peringkat berita: seberapa MUNGKIN penting & seberapa RELEVAN dgn portofolio.

Doktrin proyek: tidak ada opini tanpa data terukur. Maka skor di sini dipecah jadi
dua kelompok yang WAJIB ditampilkan terpisah di UI:

  A. TERUKUR & TERVALIDASI (dari harga, bukan teks):
     - `event_aktif`: saham sedang dalam jendela volume abnormal (vol_ratio > 1.5)
       — ini komponen yang sama yang menyetir engine event_drift (tervalidasi US
       h63). Berarti: "pasar sedang bereaksi ke sesuatu pada saham ini".
     - `composite`: skor prediktif tervalidasi saham tsb (bila ada).

  B. HEURISTIK TRANSPARAN (belum di-backtest — jangan disebut prediksi):
     - kategori berita (kata kunci: laba, M&A, regulasi, ...),
     - kekuatan sentimen FinBERT,
     - kebaruan.

`impact` hanyalah URUTAN TAMPILAN (mana yang dibaca lebih dulu), BUKAN ramalan
arah/besar pergerakan. Validasinya sedang dikumpulkan lewat jobs/news_forward_test.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

# Bobot pengurutan — dikunci a-priori, tidak di-tune ke hasil.
W_RELEVANSI = 0.40
W_KATEGORI = 0.25
W_EVENT = 0.20      # satu-satunya komponen berbasis data harga tervalidasi
W_SENTIMEN = 0.10
W_BARU = 0.05

RELEVANSI = {
    "dimiliki": 1.00,        # berita langsung tentang saham yang dimiliki
    "dipantau": 0.70,        # saham di watchlist user
    "disebut": 0.60,         # berita pasar yang menyebut nama emiten portofolio
    "sesektor": 0.35,        # emiten lain di sektor yang user miliki
    "pasar": 0.15,           # makro/pasar umum
}


def _recency(available_at) -> float:
    """1.0 (baru) -> 0.0 (>= 72 jam). Linier, transparan."""
    if available_at is None:
        return 0.0
    ts = available_at
    if isinstance(ts, str):
        return 0.5
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    return max(0.0, min(1.0, 1.0 - hours / 72.0))


def classify_relevance(item: dict, holdings: set[str], watch: set[str],
                       sector_peers: set[str]) -> tuple[str, float]:
    """Tentukan hubungan berita dgn portofolio user (deterministik, bisa diaudit)."""
    from src.ingestion.news import mentions

    sym = item.get("symbol")
    if sym:
        if sym in holdings:
            return "dimiliki", RELEVANSI["dimiliki"]
        if sym in watch:
            return "dipantau", RELEVANSI["dipantau"]
        if sym in sector_peers:
            return "sesektor", RELEVANSI["sesektor"]
    title = item.get("title", "")
    for h in holdings | watch:
        if mentions(title, h):
            return "disebut", RELEVANSI["disebut"]
    return "pasar", RELEVANSI["pasar"]


def rank(items: list[dict], holdings: set[str], watch: set[str],
         sector_peers: set[str], ctx: dict[str, dict] | None = None) -> list[dict]:
    """Urutkan berita. `ctx[symbol]` = konteks TERUKUR dari DB:
    {'vol_ratio': float, 'event_drift': float, 'composite': float|None}."""
    from src.ingestion.news import mentions

    ctx = ctx or {}
    out = []
    for it in items:
        rel_label, rel = classify_relevance(it, holdings, watch, sector_peers)
        # Feed RSS per-ticker Yahoo sering melampirkan berita yang hanya
        # bersinggungan. Bila judul tak menyebut ticker MAUPUN nama emiten,
        # tandai jujur & turunkan relevansinya — jangan diam-diam disamakan.
        sym0 = it.get("symbol")
        terkait = bool(sym0 and mentions(it.get("title", ""), sym0))
        if sym0 and not terkait:
            rel *= 0.5
            rel_label = f"{rel_label}?"
        c = ctx.get(it.get("symbol") or "", {})
        vr = c.get("vol_ratio")
        # Ambang 1.5x = ambang yang sama dipakai fitur event_drift (features/technical.py)
        event_aktif = bool(vr is not None and vr > 1.5)
        sent = abs(float(it.get("sentiment") or 0.0))
        baru = _recency(it.get("available_at"))
        kat = float(it.get("event_weight") or 0.3)

        impact = (W_RELEVANSI * rel + W_KATEGORI * kat + W_EVENT * (1.0 if event_aktif else 0.0)
                  + W_SENTIMEN * sent + W_BARU * baru)
        out.append({
            **it,
            "relevansi": rel_label,
            "judul_menyebut_emiten": terkait if sym0 else None,
            "impact": round(impact * 100, 1),
            "terukur": {                    # kelompok A — dari harga, tervalidasi
                "event_aktif": event_aktif,
                "vol_ratio": round(vr, 2) if vr is not None else None,
                "composite": c.get("composite"),
            },
            "heuristik": {                  # kelompok B — belum di-backtest
                "kategori": it.get("event_type", "umum"),
                "bobot_kategori": kat,
                "sentimen": it.get("sentiment"),
                "kebaruan": round(baru, 2),
            },
        })
    out.sort(key=lambda x: (-x["impact"], x.get("title", "")))
    return out
