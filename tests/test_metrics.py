"""Unit test metrik backtest (fungsi murni)."""
from __future__ import annotations

import numpy as np
import pytest

from src.backtest.metrics import max_drawdown, profit_factor, sharpe, wilson_ci, win_rate


def test_win_rate():
    assert win_rate([1, -1, 2, 3]) == 0.75
    assert np.isnan(win_rate([]))


def test_sharpe_sign_and_zero_vol():
    assert sharpe([0.01] * 10 + [0.02] * 10) > 0
    assert np.isnan(sharpe([0.01, 0.01, 0.01]))  # varian 0 -> nan, bukan inf


def test_max_drawdown():
    # 100 -> 120 -> 60 : drawdown = (60-120)/120 = -50%
    assert max_drawdown([100, 120, 60, 80]) == pytest.approx(-0.5)
    assert max_drawdown([1, 2, 3]) == 0.0


def test_profit_factor():
    assert profit_factor([2, -1]) == 2.0
    assert profit_factor([1, 2]) == float("inf")


def test_wilson_ci_bounds_and_levels():
    lo, hi = wilson_ci(58, 100, 0.95)
    assert 0.4 < lo < 0.58 < hi < 0.7
    lo90, hi90 = wilson_ci(58, 100, 0.90)
    assert lo90 > lo and hi90 < hi  # CI 90% lebih sempit dari 95%
    with pytest.raises(ValueError):  # audit fix: level tak didukung harus error
        wilson_ci(5, 10, 0.80)
    assert all(np.isnan(x) for x in wilson_ci(0, 0))
