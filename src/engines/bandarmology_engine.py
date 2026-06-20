"""Bandarmology Engine (Lapisan 5d) — IDX, Fase 3.

Budget $0 -> pakai PROXY (bukan broker summary asli). Confidence dibatasi & dinyatakan
eksplisit. Jangan pernah menjual proxy sebagai data broker asli (lihat 02_data_sources.md).
"""
from __future__ import annotations

from datetime import date

from src.types import EngineScore


def score(symbol: str, asof: date) -> EngineScore:
    """Skor akumulasi/distribusi (proxy bandarmology).

    TODO(impl, Fase 3):
      - foreign net flow (bila tersedia publik).
      - OBV, A/D line, Money Flow Index.
      - deteksi unusual volume + price-volume divergence.
      - confidence selalu <= 'normal' dan ditandai 'proxy' di components.
      - WAJIB lewat backtest: win-rate > 50% terukur, else bobot 0.
    """
    raise NotImplementedError("Implementasi di Fase 3.")
