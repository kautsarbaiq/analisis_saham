"""Ingestion harga EOD (US & IDX).

Sumber (pribadi/free): yfinance. Untuk versi komersial, GANTI HANYA fungsi di file ini
ke sumber berlisensi (Polygon/Tiingo) — engine di atas tidak berubah.

Tanggung jawab:
  - tarik OHLCV
  - validasi kualitas (tolak harga <= 0, volume negatif)
  - set kolom `available_at` (kapan baris ini ter-ingest)
  - kembalikan DataFrame dengan kolom sesuai skema `prices` (siap upsert)
"""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pandas as pd
import yfinance as yf

from config import settings
from config.universe import market_of

# Kolom sesuai src/storage/schema.sql tabel `prices`.
PRICE_COLS = [
    "symbol", "date", "open", "high", "low", "close",
    "adj_close", "volume", "market", "available_at",
]

# Peta nama kolom yfinance -> skema internal.
_RENAME = {
    "Date": "date", "Open": "open", "High": "high", "Low": "low",
    "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
}


def _normalize(hist: pd.DataFrame, symbol: str, available_at: datetime) -> pd.DataFrame:
    """Ubah output yfinance.history() -> DataFrame skema `prices`."""
    df = hist.reset_index()

    # yfinance kadang mengembalikan kolom MultiIndex; ratakan.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(columns=_RENAME)

    # Tanggal -> objek datetime.date (mapping bersih ke DuckDB DATE).
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date

    # Sebagian saham tak punya 'Adj Close' -> samakan dengan close.
    if "adj_close" not in df.columns:
        df["adj_close"] = df["close"]

    df["symbol"] = symbol
    df["market"] = market_of(symbol)
    df["available_at"] = available_at

    # Volume -> integer (NaN jadi 0).
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")

    return df[PRICE_COLS]


def fetch(
    symbols: list[str],
    start: date | None = None,
    end: date | None = None,
    period: str = "2y",
) -> pd.DataFrame:
    """Tarik OHLCV untuk daftar simbol, normalisasi & validasi.

    Jika `start` None -> pakai `period` (default 2 tahun, cukup untuk indikator
    seperti SMA-200). Hormati REQUEST_DELAY_SEC agar sopan ke API gratis.
    """
    available_at = datetime.now(timezone.utc).replace(tzinfo=None)
    frames: list[pd.DataFrame] = []

    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            if start is None:
                hist = tk.history(period=period, auto_adjust=False)
            else:
                hist = tk.history(start=start, end=end, auto_adjust=False)
        except Exception as exc:  # noqa: BLE001 — lanjut ke simbol berikutnya
            print(f"[prices] gagal {sym}: {exc}")
            continue

        if hist is None or hist.empty:
            print(f"[prices] kosong: {sym}")
            continue

        frames.append(_normalize(hist, sym, available_at))
        time.sleep(settings.REQUEST_DELAY_SEC)

    if not frames:
        return pd.DataFrame(columns=PRICE_COLS)

    out = pd.concat(frames, ignore_index=True)
    out, report = validate(out)
    print(f"[prices] {report}")
    return out


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Cek kualitas: harga > 0, volume >= 0. Kembalikan (df_bersih, report)."""
    n_in = len(df)
    mask = (df["close"] > 0) & (df["open"] > 0) & (df["volume"] >= 0)
    clean = df[mask].copy()
    report = {
        "rows_in": n_in,
        "rows_out": len(clean),
        "dropped": n_in - len(clean),
        "symbols": clean["symbol"].nunique() if len(clean) else 0,
    }
    return clean, report
