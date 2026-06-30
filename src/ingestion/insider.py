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


def quarters_range(start_year: int, start_q: int, end_year: int, end_q: int) -> list[tuple]:
    out = []
    y, q = start_year, start_q
    while (y, q) <= (end_year, end_q):
        out.append((y, q))
        q += 1
        if q > 4:
            q = 1; y += 1
    return out
