"""Unit test metodologi backtest: kuantil per-tanggal & walk-forward."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import quantile_test, walk_forward_quantile


def _panel_cross_sectional_edge(n_dates=30, n_sym=50, seed=7):
    """Panel sintetis: skor tinggi -> fwd lebih tinggi DI DALAM tiap tanggal."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in pd.date_range("2024-01-01", periods=n_dates, freq="B"):
        market = rng.normal(0, 3)  # guncangan pasar per-hari (noise market-timing)
        for s in range(n_sym):
            score = rng.uniform(0, 100)
            fwd = market + score * 0.02 + rng.normal(0, 0.5)  # edge seleksi murni
            rows.append({"symbol": f"S{s}", "date": d, "score": score, "fwd": fwd})
    return pd.DataFrame(rows)


def test_quantile_test_is_per_date():
    p = _panel_cross_sectional_edge()
    res = quantile_test(p, n_quantiles=5)
    # Edge seleksi (0.02 x ~80 poin skor ~ +1.6) harus tertangkap MESKI ada
    # guncangan market harian yang jauh lebih besar (per-tanggal menetralkannya).
    assert res["spread"] > 1.0
    assert res["t_stat"] > 5
    assert res["n_quantiles"] == 5


def test_walk_forward_validates_consistent_edge():
    p = _panel_cross_sectional_edge(n_dates=60)
    r = walk_forward_quantile(p, n_folds=3, n_quantiles=5)
    assert r["validated"] is True
    assert len(r["folds"]) == 3
    # audit fix: tanggal batas tidak dobel -> total n fold <= n pooled
    assert sum(f["n"] for f in r["folds"]) <= r["pooled"]["n_obs"]


def test_walk_forward_rejects_no_edge():
    rng = np.random.default_rng(3)
    rows = [{"symbol": f"S{s}", "date": d, "score": rng.uniform(0, 100),
             "fwd": rng.normal(0, 1)}
            for d in pd.date_range("2024-01-01", periods=40, freq="B")
            for s in range(40)]
    r = walk_forward_quantile(pd.DataFrame(rows), n_folds=3, n_quantiles=5)
    assert r["validated"] is False
