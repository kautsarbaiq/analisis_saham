"""Backtesting Engine (Lapisan 4) — lapisan kejujuran sistem.

Metodologi & jebakan: docs/05_backtesting.md. Mencegah look-ahead, survivorship,
overfitting, dan mengukur edge SETELAH biaya transaksi.
"""
from __future__ import annotations

from typing import Callable


def walk_forward(signal_fn: Callable, prices, folds: int | None = None):
    """Validasi walk-forward: latih di masa lalu, uji di masa depan yang belum dilihat.

    TODO(impl, Fase 1):
      - bagi timeline jadi `folds` segmen geser-maju.
      - tiap fold: bangkitkan sinyal hanya dgn data <= titik keputusan (anti look-ahead).
      - kumpulkan return out-of-sample.
    """
    raise NotImplementedError("Implementasi di Fase 1.")


def quantile_test(scores, forward_returns, n_quantiles: int = 5):
    """Uji apakah skor memisahkan kinerja: bandingkan return quantile teratas vs terbawah.

    Inti DoD Fase 1: skor-tinggi harus outperform skor-rendah secara terukur.
    """
    raise NotImplementedError("Implementasi di Fase 1.")


def evaluate_signal(signal_events, prices, cost_bps: float = 10.0):
    """Hitung metrik sebuah sinyal SETELAH biaya transaksi (slippage+fee).

    Kembalikan: win_rate, avg_return, sharpe, max_drawdown, profit_factor, N.
    """
    raise NotImplementedError("Implementasi di Fase 1.")
