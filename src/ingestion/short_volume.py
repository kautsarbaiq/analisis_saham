"""Ingestion FINRA Reg SHO daily short sale volume (GRATIS, publik, tanpa API key).

File harian pipe-delimited di CDN FINRA:
  https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt
  Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market

Sinyal kandidat (short-volume ratio): porsi volume harian yang merupakan short sale.
Literatur (Boehmer dkk.): short seller cenderung ter-informasi -> shorting tinggi =
bearish. Diuji dgn rigor standar proyek sebelum dipercaya.

Catatan jujur: ini short VOLUME (aliran harian), bukan short INTEREST (posisi
outstanding); keduanya berbeda. Short interest bi-mingguan butuh API key FINRA.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d}.txt"
UA = {"User-Agent": "ProjectBandar research pragozjawir@gmail.com"}


def _fetch_day(d: date, universe: set[str]) -> list[dict]:
    import time

    ds = d.strftime("%Y%m%d")
    txt = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL.format(d=ds), headers=UA)
            txt = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:  # libur bursa
                return []
            if e.code in (403, 429) and attempt < 3:  # rate-limit CDN -> backoff
                time.sleep(3 * (attempt + 1))
                continue
            print(f"[shortvol] {ds}: HTTP {e.code} — dilewati")
            return []
        except Exception:  # noqa: BLE001
            if attempt < 3:
                time.sleep(2)
                continue
            return []
    if txt is None:
        return []

    rows = []
    for line in txt.split("\n")[1:]:
        p = line.strip().split("|")
        if len(p) < 5 or p[1] not in universe:
            continue
        try:
            rows.append({"symbol": p[1], "date": d,
                         "short_vol": float(p[2]), "total_vol": float(p[4])})
        except ValueError:
            continue
    return rows


def fetch_range(start: date, end: date, universe: set[str], workers: int = 3) -> pd.DataFrame:
    """Unduh rentang tanggal (hari kerja) secara paralel, filter ke universe."""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)

    all_rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, rows in enumerate(ex.map(lambda x: _fetch_day(x, universe), days)):
            all_rows.extend(rows)
            if (i + 1) % 100 == 0:
                print(f"[shortvol] {i + 1}/{len(days)} hari, {len(all_rows)} baris")
    return pd.DataFrame(all_rows)
