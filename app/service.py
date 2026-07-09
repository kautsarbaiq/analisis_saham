"""Data service untuk dashboard — baca DuckDB (read-only) + hitung metrik turunan.

Dashboard TIDAK menghitung apa pun di sisi engine berat; ia hanya membaca harga lalu
menurunkan metrik ringan untuk tampilan (perubahan %, SMA, RSI, range 52 minggu).
Indikator "berat" yang dipersist ke tabel `features` menyusul di Fase 1.

Semua output sudah JSON-safe (NaN -> None).
"""
from __future__ import annotations

import json
import math

import duckdb
import pandas as pd

from config import settings


def _con() -> "duckdb.DuckDBPyConnection":
    """Koneksi read-only (server hanya membaca; batch job yang menulis)."""
    return duckdb.connect(settings.DUCKDB_PATH, read_only=True)


def _safe(x):
    """NaN/inf -> None agar valid JSON; angka -> float dibulatkan."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI Wilder (EWM)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def _load(con, symbol: str) -> pd.DataFrame:
    return con.execute(
        "SELECT date, open, high, low, close, adj_close, volume "
        "FROM prices WHERE symbol = ? ORDER BY date",
        [symbol],
    ).df()


def _metrics(df: pd.DataFrame) -> dict:
    close = df["close"]
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else last
    chg = last - prev
    rsi = _rsi(close)
    win52 = df.tail(252)
    return {
        "date": pd.Timestamp(df["date"].iloc[-1]).strftime("%Y-%m-%d"),
        "last": _safe(last),
        "prev_close": _safe(prev),
        "change": _safe(chg),
        "change_pct": _safe((chg / prev * 100) if prev else 0.0),
        "open": _safe(df["open"].iloc[-1]),
        "high": _safe(df["high"].iloc[-1]),
        "low": _safe(df["low"].iloc[-1]),
        "volume": int(df["volume"].iloc[-1]),
        "sma20": _safe(close.rolling(20).mean().iloc[-1]),
        "sma50": _safe(close.rolling(50).mean().iloc[-1]),
        "sma200": _safe(close.rolling(200).mean().iloc[-1]),
        "rsi14": _safe(rsi.iloc[-1]),
        "hi52": _safe(win52["high"].max()),
        "lo52": _safe(win52["low"].min()),
        "spark": [round(float(x), 2) for x in close.tail(30).tolist()],
    }


def _engine_map(con, engine: str) -> dict:
    """Skor DESKRIPTIF terbaru per simbol untuk satu engine (dari engine_scores)."""
    try:
        rows = con.execute(
            "SELECT symbol, score, confidence, components FROM engine_scores "
            "WHERE engine = ? "
            "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1",
            [engine],
        ).fetchall()
    except Exception:
        return {}
    out = {}
    for sym, score, conf, comp in rows:
        try:
            c = json.loads(comp) if comp else {}
        except Exception:
            c = {}
        out[sym] = {"score": _safe(score), "confidence": conf, "components": c}
    return out


def _composite_map(con) -> dict:
    """Skor prediktif composite terbaru per simbol (dari composite_scores)."""
    try:
        rows = con.execute(
            "SELECT symbol, total, breakdown, confidence FROM composite_scores "
            "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1"
        ).fetchall()
    except Exception:
        return {}
    out = {}
    for sym, total, bd, conf in rows:
        try:
            b = json.loads(bd) if bd else {}
        except Exception:
            b = {}
        out[sym] = {"total": _safe(total), "breakdown": b, "confidence": conf}
    return out


def validation() -> list[dict]:
    """Vonis backtest per engine PER MARKET (apakah skornya punya edge terukur)."""
    con = _con()
    try:
        rows = con.execute(
            "SELECT engine, horizon_days, market, top_mean, bottom_mean, spread, "
            "t_stat, validated, note FROM validation "
            "ORDER BY market, validated DESC, engine, horizon_days"
        ).fetchall()
    except Exception:
        return []
    finally:
        con.close()
    return [{
        "engine": r[0], "horizon_days": r[1], "market": r[2], "top_mean": _safe(r[3]),
        "bottom_mean": _safe(r[4]), "spread": _safe(r[5]), "t_stat": _safe(r[6]),
        "validated": bool(r[7]), "note": r[8],
    } for r in rows]


def watchlist() -> list[dict]:
    """Metrik ringkas + posture teknikal semua simbol untuk panel watchlist."""
    con = _con()
    out: list[dict] = []
    try:
        pmap = _engine_map(con, "technical")
        fmap = _engine_map(con, "fundamental")
        mmap = _engine_map(con, "mean_reversion")
        imap = _engine_map(con, "insider")
        svmap = _engine_map(con, "shortvol_level")
        cmap = _composite_map(con)
        # Satu query untuk semua harga (jauh lebih cepat utk universe 500+).
        big = con.execute(
            "SELECT symbol, date, open, high, low, close, adj_close, volume "
            "FROM prices ORDER BY symbol, date"
        ).df()
        for s, df in big.groupby("symbol", sort=False):
            if df.empty:
                continue
            m = _metrics(df.reset_index(drop=True))
            m["symbol"] = s
            p = pmap.get(s)
            if p:
                m["posture"] = p["score"]
                m["posture_conf"] = p["confidence"]
                m["posture_comp"] = p["components"]
            f = fmap.get(s)
            if f:
                m["fundamental"] = f["score"]
                m["fundamental_conf"] = f["confidence"]
                m["fundamental_comp"] = f["components"]
            mm = mmap.get(s)
            if mm:
                m["mr"] = mm["score"]
                m["mr_comp"] = mm["components"]
            im = imap.get(s)
            if im:
                m["insider"] = im["score"]
                m["insider_buys"] = (im["components"] or {}).get("buys_90d", 0)
            svm = svmap.get(s)
            if svm:
                m["shortvol"] = svm["score"]
                m["shortvol_svr5"] = (svm["components"] or {}).get("svr5")
            c = cmap.get(s)
            if c:
                m["composite"] = c["total"]
                m["composite_conf"] = c["confidence"]
                m["composite_breakdown"] = c["breakdown"]
            out.append(m)
    finally:
        con.close()
    # Screener: urut skor PREDIKTIF (composite) tertinggi dulu (None paling akhir).
    out.sort(key=lambda m: (m.get("composite") is None, -(m.get("composite") or 0)))
    return out


def ohlc(symbol: str, limit: int = 400) -> dict:
    """Bar OHLC + volume + garis SMA untuk charting (TradingView lightweight-charts)."""
    con = _con()
    try:
        df = _load(con, symbol)
    finally:
        con.close()
    if df.empty:
        return {"symbol": symbol, "bars": [], "volume": [], "sma20": [], "sma50": []}

    df = df.copy()
    df["sma20"] = df["close"].rolling(20).mean()
    df["sma50"] = df["close"].rolling(50).mean()
    df = df.tail(limit)

    bars, volume, sma20, sma50 = [], [], [], []
    for _, r in df.iterrows():
        t = pd.Timestamp(r["date"]).strftime("%Y-%m-%d")
        up = r["close"] >= r["open"]
        bars.append({
            "time": t,
            "open": round(float(r["open"]), 2),
            "high": round(float(r["high"]), 2),
            "low": round(float(r["low"]), 2),
            "close": round(float(r["close"]), 2),
        })
        volume.append({
            "time": t,
            "value": int(r["volume"]),
            "color": "rgba(38,166,154,0.5)" if up else "rgba(239,83,80,0.5)",
        })
        if not pd.isna(r["sma20"]):
            sma20.append({"time": t, "value": round(float(r["sma20"]), 2)})
        if not pd.isna(r["sma50"]):
            sma50.append({"time": t, "value": round(float(r["sma50"]), 2)})

    return {"symbol": symbol, "bars": bars, "volume": volume, "sma20": sma20, "sma50": sma50}
