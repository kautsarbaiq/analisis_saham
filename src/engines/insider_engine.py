"""Insider Engine — sinyal smart-money INDEPENDEN (SEC Form 4 'P'), TERVALIDASI.

Skor dari intensitas pembelian insider pasar-terbuka dalam 90 hari terakhir (data
bulk Form 345). Edge tervalidasi: abnormal +0.22%/21h, 3/3 periode positif (t 2.42).

Non-pembeli = 50 (NETRAL, bukan bearish — tidak ada info). Pembeli dapat bonus naik
sesuai jumlah pembelian. CATATAN: data bulk SEC kuartalan -> sinyal live lag ~1 kuartal
(real-time butuh fetch Form 4 per emiten; arah pengembangan).
"""
from __future__ import annotations

from datetime import date

from src.types import EngineScore


def score(symbol: str, n_buys_90d: int, as_of: date, stale: bool = False) -> EngineScore:
    """Skor insider. 50 = NETRAL (tidak ada pembelian = bukan info buruk, jadi
    confidence tetap normal — audit fix: dulu 'low' utk non-pembeli membuat composite
    produksi menyimpang dari simulasi track-record). `stale=True` (data bulk >45 hari
    tertinggal) -> confidence 'low' utk SEMUA simbol (bobot dipangkas otomatis)."""
    sc = 50.0 + min(50.0, n_buys_90d * 12.5) if n_buys_90d else 50.0
    return EngineScore(
        symbol=symbol, as_of=as_of, engine="insider",
        score=round(sc, 2),
        components={"buys_90d": int(n_buys_90d), "stale": bool(stale)},
        sample_size=None, confidence="low" if stale else "normal",
    )
