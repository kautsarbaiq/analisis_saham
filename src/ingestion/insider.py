"""Ingestion insider trading dari SEC bulk Form 345 datasets (GRATIS, terstruktur).

Sinyal "smart money" INDEPENDEN dari harga/fundamental: pembelian saham pasar-terbuka
(TRANS_CODE='P') oleh orang dalam. Secara akademik punya edge (Lakonishok & Lee 2001;
cluster buying terkuat).

Sumber: dataset kuartalan Form 345 (TSV). Join SUBMISSION (ticker, FILING_DATE) +
NONDERIV_TRANS (kode, shares, harga). FILING_DATE = saat publik tahu -> anti look-ahead.
"""
from __future__ import annotations

import io
import urllib.request
import zipfile

import pandas as pd

from config.universe import US_UNIVERSE

BASE = ("https://www.sec.gov/files/structureddata/data/"
        "insider-transactions-data-sets/{y}q{q}_form345.zip")
UA = {"User-Agent": "ProjectBandar research pragozjawir@gmail.com"}


def fetch_quarter(year: int, q: int, universe: set[str] | None = None) -> pd.DataFrame:
    """Unduh 1 kuartal, kembalikan DataFrame pembelian pasar-terbuka (code P) utk universe."""
    universe = universe or set(US_UNIVERSE)
    url = BASE.format(y=year, q=q)
    try:
        data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
    except Exception as exc:  # noqa: BLE001
        print(f"[insider] {year}Q{q} gagal: {exc}")
        return pd.DataFrame()

    z = zipfile.ZipFile(io.BytesIO(data))
    sub = pd.read_csv(z.open("SUBMISSION.tsv"), sep="\t", dtype=str,
                      usecols=["ACCESSION_NUMBER", "FILING_DATE", "ISSUERTRADINGSYMBOL"])
    tr = pd.read_csv(z.open("NONDERIV_TRANS.tsv"), sep="\t", dtype=str,
                     usecols=["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE",
                              "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    tr = tr[(tr["TRANS_CODE"] == "P") & (tr["TRANS_ACQUIRED_DISP_CD"] == "A")]  # beli pasar terbuka
    m = tr.merge(sub, on="ACCESSION_NUMBER", how="left")
    m["sym"] = m["ISSUERTRADINGSYMBOL"].str.upper()
    m = m[m["sym"].isin(universe)]
    if m.empty:
        return pd.DataFrame()

    out = pd.DataFrame({
        "symbol": m["sym"],
        "trans_date": pd.to_datetime(m["TRANS_DATE"], format="%d-%b-%Y", errors="coerce"),
        "filing_date": pd.to_datetime(m["FILING_DATE"], format="%d-%b-%Y", errors="coerce"),
        "shares": pd.to_numeric(m["TRANS_SHARES"], errors="coerce"),
        "price": pd.to_numeric(m["TRANS_PRICEPERSHARE"], errors="coerce"),
        "accession": m["ACCESSION_NUMBER"],
    }).dropna(subset=["filing_date", "shares", "price"])
    out["value"] = out["shares"] * out["price"]
    out = out[out["value"] > 0]
    print(f"[insider] {year}Q{q}: {len(out)} pembelian (universe), {out['symbol'].nunique()} emiten")
    return out


def _get_text(url: str) -> str | None:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers=UA)
        return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return None


@__import__("functools").lru_cache(maxsize=1)
def _cik_map() -> dict:
    from src.ingestion.fundamentals import load_cik_map
    return load_cik_map()


def recent_buys(symbol: str, max_filings: int = 40, days: int = 120) -> list[dict]:
    """REAL-TIME: pembelian insider pasar-terbuka (code P) terbaru via Form 4 langsung.

    Menghilangkan lag data bulk kuartalan. Fetch on-demand per emiten (beberapa detik).
    Kembalikan list {date, owner, role, shares, price, value} terbaru -> terlama.
    """
    import datetime as _dt
    import re
    import xml.etree.ElementTree as ET

    from src.ingestion.fundamentals import _get_json

    cik = _cik_map().get(symbol.upper())
    if not cik:
        return []
    sub = _get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
    if not sub:
        return []
    rec = sub["filings"]["recent"]
    cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()

    out, seen = [], 0
    for i, form in enumerate(rec["form"]):
        if form != "4":
            continue
        if rec["filingDate"][i] < cutoff:
            break  # "recent" terurut terbaru->terlama
        seen += 1
        if seen > max_filings:
            break
        acc = rec["accessionNumber"][i].replace("-", "")
        raw = re.sub(r"^xsl[^/]+/", "", rec["primaryDocument"][i])
        txt = _get_text(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{raw}")
        if not txt or "ownershipDocument" not in txt:
            continue
        try:
            root = ET.fromstring(txt)
        except Exception:  # noqa: BLE001
            continue
        owner = root.findtext(".//reportingOwnerId/rptOwnerName") or "?"
        reln = root.find(".//reportingOwnerRelationship")
        role = "Insider"
        if reln is not None:
            role = (reln.findtext("officerTitle")
                    or ("Director" if reln.findtext("isDirector") in ("1", "true") else "Insider"))
        for tx in root.findall(".//nonDerivativeTransaction"):
            if tx.findtext(".//transactionCoding/transactionCode") != "P":
                continue
            try:
                sh = float(tx.findtext(".//transactionShares/value") or 0)
                px = float(tx.findtext(".//transactionPricePerShare/value") or 0)
            except ValueError:
                continue
            out.append({
                "date": tx.findtext(".//transactionDate/value") or "",
                "owner": owner, "role": role,
                "shares": int(sh), "price": round(px, 2), "value": int(sh * px),
            })
    return out


def quarters_range(start_year: int, start_q: int, end_year: int, end_q: int) -> list[tuple]:
    out = []
    y, q = start_year, start_q
    while (y, q) <= (end_year, end_q):
        out.append((y, q))
        q += 1
        if q > 4:
            q = 1; y += 1
    return out
