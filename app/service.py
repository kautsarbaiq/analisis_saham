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


def symbols() -> list[str]:
    con = _con()
    try:
        rows = con.execute("SELECT DISTINCT symbol FROM prices ORDER BY symbol").fetchall()
    finally:
        con.close()
    return [r[0] for r in rows]


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


def validation() -> list[dict]:
    """Vonis backtest per engine (apakah skornya punya edge terukur)."""
    con = _con()
    try:
        rows = con.execute(
            "SELECT engine, horizon_days, top_mean, bottom_mean, spread, t_stat, "
            "validated, note FROM validation ORDER BY engine, horizon_days"
        ).fetchall()
    except Exception:
        return []
    finally:
        con.close()
    return [{
        "engine": r[0], "horizon_days": r[1], "top_mean": _safe(r[2]),
        "bottom_mean": _safe(r[3]), "spread": _safe(r[4]), "t_stat": _safe(r[5]),
        "validated": bool(r[6]), "note": r[7],
    } for r in rows]


def watchlist() -> list[dict]:
    """Metrik ringkas + posture teknikal semua simbol untuk panel watchlist."""
    con = _con()
    out: list[dict] = []
    try:
        pmap = _engine_map(con, "technical")
        fmap = _engine_map(con, "fundamental")
        for s in symbols():
            df = _load(con, s)
            if df.empty:
                continue
            m = _metrics(df)
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
            out.append(m)
    finally:
        con.close()
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
