"""Metrik performa terukur (dipakai backtest & Track Record).

Semua fungsi murni (numpy saja), mudah diuji & tanpa efek samping.
"""
from __future__ import annotations

from math import sqrt

import numpy as np


def _clean(x) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    return a[~np.isnan(a)]


def win_rate(returns) -> float:
    """% observasi dengan arah benar (>0)."""
    r = _clean(returns)
    return float((r > 0).mean()) if len(r) else float("nan")


def sharpe(returns, periods_per_year: int = 252) -> float:
    """Sharpe ratio disetahunkan."""
    r = _clean(returns)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * sqrt(periods_per_year))


def max_drawdown(equity_curve) -> float:
    """Penurunan puncak-ke-lembah terburuk (fraksi negatif)."""
    e = np.asarray(equity_curve, dtype=float)
    if len(e) == 0:
        return float("nan")
    peak = np.maximum.accumulate(e)
    return float(((e - peak) / peak).min())


def profit_factor(returns) -> float:
    """Total profit / total loss."""
    r = _clean(returns)
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    return float(gains / losses) if losses > 0 else float("inf")


def wilson_ci(successes: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Confidence interval Wilson untuk proporsi (stabil untuk N kecil)."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.959963984540054 if abs(level - 0.95) < 1e-6 else 1.6448536269514722
    p = successes / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def welch_t(a, b) -> float:
    """Statistik t Welch (dua sampel, varians tak sama). Tanpa scipy."""
    a, b = _clean(a), _clean(b)
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    se = sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    return float((a.mean() - b.mean()) / se) if se > 0 else float("nan")
