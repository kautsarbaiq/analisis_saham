"""Ingestion fundamental dari SEC EDGAR (US).

SEC EDGAR = sumber resmi, public domain, AMAN untuk komersial. Wajib kirim header
User-Agent berisi email (aturan SEC) -> settings.SEC_USER_AGENT.

Anti look-ahead: simpan `filed_at` (kapan laporan dirilis), bukan hanya `period`.
Backtest hanya boleh memakai fundamental yang `filed_at <= asof`.

Strategi: ambil snapshot TAHUNAN (10-K/20-F) untuk tiap metrik kunci, lalu turunkan
rasio di features/fundamental.py. Snapshot tahunan memberi deret YoY bersih untuk
Piotroski F-Score & pertumbuhan.
"""
from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import requests

from config import settings

CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F"}
# Metrik ALIRAN (durasi) — wajib difilter ke periode ~1 tahun agar tidak tertukar
# dengan angka kuartalan yang juga muncul di dalam 10-K. Sisanya = neraca (instan).
FLOW_METRICS = {"revenue", "net_income", "gross_profit", "operating_income", "cfo",
                "eps_diluted", "shares_diluted"}

# Metrik kanonik -> daftar tag XBRL (fallback berurutan; emiten pakai tag berbeda).
TAGS: dict[str, list[str]] = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "assets_current": ["AssetsCurrent"],
    "liabilities_current": ["LiabilitiesCurrent"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic"],
}


def _ua() -> str:
    return settings.SEC_USER_AGENT or "Project Bandar research pragozjawir@gmail.com"


def _get_json(url: str) -> dict | None:
    try:
        r = requests.get(url, headers={"User-Agent": _ua(), "Accept-Encoding": "gzip"}, timeout=30)
        if r.status_code != 200:
            print(f"[fundamentals] HTTP {r.status_code} {url}")
            return None
        return r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[fundamentals] gagal GET {url}: {exc}")
        return None


def load_cik_map() -> dict[str, str]:
    """ticker -> CIK 10-digit (zero-padded)."""
    data = _get_json(CIK_MAP_URL)
    if not data:
        return {}
    out = {}
    for row in data.values():
        out[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
    return out


def _extract(facts: dict, symbol: str) -> list[dict]:
    """Ambil snapshot tahunan tiap metrik dari companyfacts -> baris skema fundamentals."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    rows: list[dict] = []
    for metric, tag_list in TAGS.items():
        # Gabungkan SEMUA tag fallback (emiten ganti tag lintas tahun, mis. ASC 606),
        # dedup per period-end dgn `filed` terbaru (anti restatement lama).
        best: dict[str, dict] = {}
        for tag in tag_list:
            node = gaap.get(tag)
            if not node:
                continue
            units = node.get("units", {})
            unit_key = next(iter(units), None)  # 'USD' | 'USD/shares' | 'shares'
            if not unit_key:
                continue
            for e in units[unit_key]:
                if e.get("form") not in ANNUAL_FORMS or "end" not in e or e.get("val") is None:
                    continue
                if metric in FLOW_METRICS:
                    start = e.get("start")
                    if not start:
                        continue
                    days = (pd.to_datetime(e["end"]) - pd.to_datetime(start)).days
                    if not (350 <= days <= 380):  # hanya periode setahun penuh
                        continue
                end = e["end"]
                if end not in best or e.get("filed", "") > best[end].get("filed", ""):
                    best[end] = e
        for end, e in best.items():
            rows.append({
                "symbol": symbol,
                "period": pd.to_datetime(end).date(),
                "metric": metric,
                "value": float(e["val"]),
                "filed_at": pd.to_datetime(e.get("filed", end)),
            })
    return rows


def fetch(symbols: list[str]) -> pd.DataFrame:
    """Tarik fundamental tahunan SEC EDGAR untuk daftar simbol (US saja)."""
    cik_map = load_cik_map()
    if not cik_map:
        print("[fundamentals] gagal memuat peta CIK; lewati.")
        return pd.DataFrame(columns=["symbol", "period", "metric", "value", "filed_at"])

    all_rows: list[dict] = []
    for sym in symbols:
        if sym.upper().endswith(".JK"):
            continue  # SEC hanya untuk emiten US
        cik = cik_map.get(sym.upper())
        if not cik:
            print(f"[fundamentals] CIK tak ditemukan: {sym}")
            continue
        facts = _get_json(FACTS_URL.format(cik=cik))
        if facts:
            rows = _extract(facts, sym)
            all_rows.extend(rows)
            print(f"[fundamentals] {sym}: {len(rows)} titik metrik tahunan")
        time.sleep(max(settings.REQUEST_DELAY_SEC, 0.2))  # sopan ke SEC

    if not all_rows:
        return pd.DataFrame(columns=["symbol", "period", "metric", "value", "filed_at"])
    return pd.DataFrame(all_rows)
