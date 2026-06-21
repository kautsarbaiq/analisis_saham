"""Ingestion GDELT — tone & volume berita historis (event-study berbasis TEKS).

GDELT DOC 2.0 API gratis & historis, TAPI rate-limited ketat (429 sering) -> backoff
wajib, dan jendela via API terbatas (~6-24 bln). Untuk skala penuh (500 saham,
multi-tahun) -> butuh GDELT BigQuery (free tier, perlu akun GCP). Modul ini cocok
untuk sampel kecil / per-saham, melengkapi sinyal event-drift berbasis harga.

`tone` = rata-rata sentimen artikel/hari (skala GDELT, ~-10..+10). `vol` = intensitas
liputan (% artikel menyebut query).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

DOC = "https://api.gdeltproject.org/api/v2/doc/doc"
_UA = "ProjectBandar/0.1 (research)"


def _query(query: str, mode: str, timespan: str = "12m", tries: int = 4, backoff: int = 20):
    url = DOC + "?" + urllib.parse.urlencode(
        {"query": query, "mode": mode, "format": "json", "timespan": timespan})
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            return json.load(urllib.request.urlopen(req, timeout=45))
        except urllib.error.HTTPError as e:
            if e.code == 429 and k < tries - 1:
                time.sleep(backoff)
                continue
            return None
        except Exception:  # noqa: BLE001
            return None
    return None


def tone_timeline(symbol: str, name: str | None = None, timespan: str = "12m") -> list[dict]:
    """Deret harian {date(YYYYMMDD), tone, vol} liputan berita satu emiten.

    Aman: kembalikan [] bila gagal/terblok. Hormati rate-limit (jeda antar pemanggilan
    harus diatur oleh pemanggil untuk batch).
    """
    q = f'"{name or symbol}" (stock OR shares OR earnings OR {symbol})'
    merged: dict[str, dict] = {}

    dt = _query(q, "timelinetone", timespan)
    if dt and dt.get("timeline"):
        for p in dt["timeline"][0]["data"]:
            merged.setdefault(p["date"][:8], {})["tone"] = p["value"]

    dv = _query(q, "timelinevol", timespan)
    if dv and dv.get("timeline"):
        for p in dv["timeline"][0]["data"]:
            merged.setdefault(p["date"][:8], {})["vol"] = p["value"]

    return [{"date": d, "tone": v.get("tone"), "vol": v.get("vol")}
            for d, v in sorted(merged.items())]
