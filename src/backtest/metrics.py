"""Metrik performa terukur (dipakai backtest & Track Record).

Semua fungsi murni (pure) agar mudah diuji unit dan tidak ada efek samping.
"""
from __future__ import annotations


def win_rate(returns) -> float:
    """% observasi dengan arah benar."""
    raise NotImplementedError


def sharpe(returns, periods_per_year: int = 252) -> float:
    """Sharpe ratio tahunan."""
    raise NotImplementedError


def max_drawdown(equity_curve) -> float:
    """Penurunan puncak-ke-lembah terburuk."""
    raise NotImplementedError


def profit_factor(returns) -> float:
    """Total profit / total loss."""
    raise NotImplementedError


def wilson_ci(successes: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Confidence interval Wilson untuk proporsi (win-rate). Stabil utk N kecil.

    Dipakai agar klaim "win-rate 58%" selalu menyertakan rentang ketidakpastian.
    """
    raise NotImplementedError
