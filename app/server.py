"""FastAPI backend untuk dashboard terminal Project Bandar.

Server HANYA membaca DuckDB (read-only) dan menyajikan JSON + halaman statis.
Semua komputasi berat dilakukan oleh batch job (jobs/daily_us.py), bukan di request.

Jalankan:  .venv/bin/uvicorn app.server:app --reload --port 8000
Buka:      http://localhost:8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import service

app = FastAPI(title="Project Bandar — Terminal", version="0.1.0")

STATIC = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/api/watchlist")
def api_watchlist() -> list[dict]:
    return service.watchlist()


@app.get("/api/validation")
def api_validation() -> list[dict]:
    return service.validation()


@app.get("/api/track_record")
def api_track_record() -> dict:
    import json
    from pathlib import Path
    f = Path(__file__).parent.parent / "snapshots" / "track_record.json"
    if not f.exists():
        return {"metrics": {}, "curve": []}
    return json.loads(f.read_text())


@app.get("/api/ohlc/{symbol}")
def api_ohlc(symbol: str) -> dict:
    data = service.ohlc(symbol.upper())
    if not data["bars"]:
        raise HTTPException(status_code=404, detail=f"Tidak ada data untuk {symbol}")
    return data


@app.get("/api/news/{symbol}")
def api_news(symbol: str) -> dict:
    from src.ingestion.news import aggregate_sentiment, fetch_rss
    items = fetch_rss(symbol.upper())
    return {"symbol": symbol.upper(), "items": items, "summary": aggregate_sentiment(items)}


# Cache insider real-time (audit fix: tanpa cache, tiap klik simbol memicu hingga
# 40 fetch SEC sekuensial). TTL 1 jam — Form 4 tidak berubah semenit-menit.
_INSIDER_CACHE: dict[str, tuple[float, dict]] = {}
_INSIDER_TTL = 3600.0


@app.get("/api/insider/{symbol}")
def api_insider(symbol: str) -> dict:
    import time as _time

    from src.ingestion.insider import recent_buys

    sym = symbol.upper()
    hit = _INSIDER_CACHE.get(sym)
    if hit and _time.time() - hit[0] < _INSIDER_TTL:
        return hit[1]
    buys = recent_buys(sym, days=180)
    payload = {
        "symbol": sym, "buys": buys[:8], "count": len(buys),
        "total_value": sum(b["value"] for b in buys),
        "n_insiders": len({b["owner"] for b in buys}),
    }
    _INSIDER_CACHE[sym] = (_time.time(), payload)
    return payload


# Static assets (css/js) di /static.
app.mount("/static", StaticFiles(directory=STATIC), name="static")
