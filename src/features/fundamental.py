"""Feature store fundamental (Lapisan 3) — rasio & skor dari fakta SEC EDGAR.

Mengubah fakta mentah tahunan (tabel `fundamentals`) menjadi rasio terukur + skor
komposit 0..100. Memakai dua tahun terakhir untuk YoY (Piotroski, pertumbuhan).

Semua perhitungan transparan & disimpan sebagai komponen audit. Sama seperti teknikal:
skor fundamental WAJIB di-backtest sebelum dipercaya sebagai sinyal (docs/05).
"""
from __future__ import annotations

import pandas as pd

CORE = ["net_income", "assets", "equity"]  # minimal untuk skor bermakna


def _clamp(x: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, x))


def _safe_div(a, b):
    if a is None or b is None or b == 0:
        return None
    return a / b


def _g(row: pd.Series, col: str):
    if col not in row:
        return None
    v = row[col]
    return float(v) if pd.notna(v) else None


def _piotroski(cur: pd.Series, prev: pd.Series) -> tuple[int, int]:
    """F-Score Piotroski (0..9). Kembalikan (poin, kriteria_terhitung)."""
    pts = 0
    avail = 0

    def add(cond):
        nonlocal pts, avail
        if cond is None:
            return
        avail += 1
        pts += 1 if cond else 0

    ni_c, ni_p = _g(cur, "net_income"), _g(prev, "net_income")
    a_c, a_p = _g(cur, "assets"), _g(prev, "assets")
    cfo_c = _g(cur, "cfo")
    roa_c, roa_p = _safe_div(ni_c, a_c), _safe_div(ni_p, a_p)

    add(roa_c > 0 if roa_c is not None else None)                       # 1 ROA>0
    add(cfo_c > 0 if cfo_c is not None else None)                       # 2 CFO>0
    add(roa_c > roa_p if (roa_c is not None and roa_p is not None) else None)  # 3 ΔROA
    add(cfo_c > ni_c if (cfo_c is not None and ni_c is not None) else None)    # 4 akrual
    # 5 ΔLeverage (LTD/assets) turun
    lev_c = _safe_div(_g(cur, "long_term_debt"), a_c)
    lev_p = _safe_div(_g(prev, "long_term_debt"), a_p)
    add(lev_c < lev_p if (lev_c is not None and lev_p is not None) else None)
    # 6 ΔCurrent ratio naik
    cr_c = _safe_div(_g(cur, "assets_current"), _g(cur, "liabilities_current"))
    cr_p = _safe_div(_g(prev, "assets_current"), _g(prev, "liabilities_current"))
    add(cr_c > cr_p if (cr_c is not None and cr_p is not None) else None)
    # 7 tidak ada dilusi
    sh_c, sh_p = _g(cur, "shares_diluted"), _g(prev, "shares_diluted")
    add(sh_c <= sh_p if (sh_c is not None and sh_p is not None) else None)
    # 8 ΔGross margin naik
    gm_c = _safe_div(_g(cur, "gross_profit"), _g(cur, "revenue"))
    gm_p = _safe_div(_g(prev, "gross_profit"), _g(prev, "revenue"))
    add(gm_c > gm_p if (gm_c is not None and gm_p is not None) else None)
    # 9 ΔAsset turnover naik
    at_c = _safe_div(_g(cur, "revenue"), a_c)
    at_p = _safe_div(_g(prev, "revenue"), a_p)
    add(at_c > at_p if (at_c is not None and at_p is not None) else None)

    return pts, avail


def _altman_z(cur: pd.Series, price: float | None) -> float | None:
    """Altman Z-Score (model umum). X4 (mkt cap/total liabilities) butuh harga."""
    a = _g(cur, "assets")
    if not a:
        return None
    wc = None
    ca, cl = _g(cur, "assets_current"), _g(cur, "liabilities_current")
    if ca is not None and cl is not None:
        wc = ca - cl
    x1 = _safe_div(wc, a) or 0
    x2 = _safe_div(_g(cur, "retained_earnings"), a) or 0
    x3 = _safe_div(_g(cur, "operating_income"), a) or 0
    x5 = _safe_div(_g(cur, "revenue"), a) or 0
    x4 = 0
    shares = _g(cur, "shares_diluted")
    tl = _g(cur, "liabilities")
    if price and shares and tl:
        x4 = (price * shares) / tl
    return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5


def compute(symbol: str, fundamentals_df: pd.DataFrame, price: float | None = None) -> dict | None:
    """Hitung rasio + sub-skor + fundamental_score (0..100) untuk satu simbol.

    Kembalikan dict (komponen audit + skor) atau None bila data tak memadai.
    """
    if fundamentals_df is None or fundamentals_df.empty:
        return None
    wide = fundamentals_df.pivot_table(index="period", columns="metric", values="value", aggfunc="last").sort_index()
    if len(wide) == 0 or not all(c in wide.columns for c in CORE):
        return None

    cur = wide.iloc[-1]
    prev = wide.iloc[-2] if len(wide) >= 2 else None

    ni, eq, a = _g(cur, "net_income"), _g(cur, "equity"), _g(cur, "assets")
    rev = _g(cur, "revenue")
    roe = _safe_div(ni, eq)
    roa = _safe_div(ni, a)
    net_margin = _safe_div(ni, rev)
    gross_margin = _safe_div(_g(cur, "gross_profit"), rev)
    op_margin = _safe_div(_g(cur, "operating_income"), rev)
    current_ratio = _safe_div(_g(cur, "assets_current"), _g(cur, "liabilities_current"))
    debt_to_equity = _safe_div(_g(cur, "liabilities"), eq)
    rev_growth = (_safe_div(rev, _g(prev, "revenue")) - 1) if (prev is not None and _g(prev, "revenue")) else None
    eps_c, eps_p = _g(cur, "eps_diluted"), (_g(prev, "eps_diluted") if prev is not None else None)
    eps_growth = (eps_c / eps_p - 1) if (eps_c is not None and eps_p and eps_p > 0) else None

    pio_pts, pio_avail = _piotroski(cur, prev if prev is not None else pd.Series(dtype=float))
    altman = _altman_z(cur, price)

    # --- Sub-skor 0..100 ---
    sub = {}
    if pio_avail >= 5:
        sub["quality"] = pio_pts / 9 * 100
    prof_parts = [s for s in [
        _clamp(roe * 400) if roe is not None else None,        # ROE 25% -> 100
        _clamp(net_margin * 500) if net_margin is not None else None,  # NM 20% -> 100
        _clamp(op_margin * 333) if op_margin is not None else None,    # OM 30% -> 100
    ] if s is not None]
    if prof_parts:
        sub["profitability"] = sum(prof_parts) / len(prof_parts)
    growth_parts = [_clamp(50 + g * 250) for g in [rev_growth, eps_growth] if g is not None]
    if growth_parts:
        sub["growth"] = sum(growth_parts) / len(growth_parts)
    health_parts = []
    if altman is not None:
        health_parts.append(_clamp((altman - 1.8) / (3.0 - 1.8) * 100))
    if current_ratio is not None:
        health_parts.append(_clamp((current_ratio - 1.0) / (2.0 - 1.0) * 100))
    if health_parts:
        sub["health"] = sum(health_parts) / len(health_parts)

    weights = {"quality": 0.30, "profitability": 0.30, "growth": 0.20, "health": 0.20}
    wsum = sum(weights[k] for k in sub)
    fundamental_score = sum(sub[k] * weights[k] for k in sub) / wsum if wsum else None

    def r(x, nd=2):
        return round(float(x), nd) if x is not None else None

    return {
        "as_of_period": str(cur.name.date()) if hasattr(cur.name, "date") else str(cur.name),
        "score": r(fundamental_score, 1),
        "sub_scores": {k: round(v, 1) for k, v in sub.items()},
        "piotroski": pio_pts, "piotroski_avail": pio_avail,
        "altman_z": r(altman),
        "roe": r(roe), "roa": r(roa), "net_margin": r(net_margin),
        "gross_margin": r(gross_margin), "op_margin": r(op_margin),
        "current_ratio": r(current_ratio), "debt_to_equity": r(debt_to_equity),
        "rev_growth": r(rev_growth), "eps_growth": r(eps_growth),
        "years": int(len(wide)),
    }
