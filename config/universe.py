"""Daftar saham yang dipantau (universe).

US: konstituen S&P 500 dari config/sp500.csv (di-commit -> backtest reproducible).
Bila file hilang, fallback ke 15 mega-cap. IDX ditambahkan di Fase 3.

Universe eksplisit & ter-commit penting: hasil backtest hanya valid jika universe-nya
tetap. Perubahan universe = re-backtest.
"""
from __future__ import annotations

import csv
from pathlib import Path

_SP500_FILE = Path(__file__).parent / "sp500.csv"

# Fallback bila sp500.csv tidak ada (mis. fresh checkout sebelum fetch).
_FALLBACK_US: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    "JPM", "V", "WMT", "XOM", "UNH", "JNJ", "PG", "HD",
]


def _load_sp500() -> list[str]:
    if not _SP500_FILE.exists():
        return []
    with open(_SP500_FILE) as f:
        return [r["symbol"].strip().upper() for r in csv.DictReader(f) if r.get("symbol")]


# Sektor IDX (LQ45) — klasifikasi manual ala IDX-IC, dikelompokkan agar tiap bucket
# cukup besar utk sector-neutralization (demean per tanggal x sektor).
IDX_SECTORS: dict[str, str] = {
    # Financials (bank)
    "BBCA.JK": "Financials", "BBRI.JK": "Financials", "BMRI.JK": "Financials",
    "BBNI.JK": "Financials", "ARTO.JK": "Financials",
    # Infrastruktur / telco / menara
    "TLKM.JK": "Telco-Infra", "EXCL.JK": "Telco-Infra", "ISAT.JK": "Telco-Infra",
    "TOWR.JK": "Telco-Infra", "TBIG.JK": "Telco-Infra",
    # Energi (batubara, migas, distribusi)
    "ADRO.JK": "Energy", "PTBA.JK": "Energy", "ITMG.JK": "Energy", "ADMR.JK": "Energy",
    "INDY.JK": "Energy", "MEDC.JK": "Energy", "PGAS.JK": "Energy", "AKRA.JK": "Energy",
    # Basic materials (logam, semen, petrokimia, pulp)
    "ANTM.JK": "Basic-Mat", "MDKA.JK": "Basic-Mat", "INCO.JK": "Basic-Mat",
    "SMGR.JK": "Basic-Mat", "TPIA.JK": "Basic-Mat", "BRPT.JK": "Basic-Mat",
    "INKP.JK": "Basic-Mat",
    # Consumer non-cyclical (+ farmasi)
    "UNVR.JK": "Consumer-NC", "ICBP.JK": "Consumer-NC", "INDF.JK": "Consumer-NC",
    "GGRM.JK": "Consumer-NC", "HMSP.JK": "Consumer-NC", "CPIN.JK": "Consumer-NC",
    "JPFA.JK": "Consumer-NC", "KLBF.JK": "Consumer-NC",
    # Consumer cyclical / ritel / media
    "AMRT.JK": "Consumer-Cyc", "ACES.JK": "Consumer-Cyc", "ERAA.JK": "Consumer-Cyc",
    "MAPI.JK": "Consumer-Cyc", "MNCN.JK": "Consumer-Cyc",
    # Teknologi
    "GOTO.JK": "Tech", "BUKA.JK": "Tech",
    # Properti
    "BSDE.JK": "Property", "CTRA.JK": "Property", "PWON.JK": "Property",
    # Industrials (konglomerat otomotif, alat berat)
    "ASII.JK": "Industrials", "UNTR.JK": "Industrials",
}


def load_sectors() -> dict[str, str]:
    """Peta ticker -> sektor: GICS utk US (sp500.csv) + IDX_SECTORS utk .JK.
    Dipakai sector-neutralization (demean per tanggal x sektor)."""
    out: dict[str, str] = dict(IDX_SECTORS)
    if _SP500_FILE.exists():
        with open(_SP500_FILE) as f:
            out.update({r["symbol"].strip().upper(): (r.get("sector") or "?").strip()
                        for r in csv.DictReader(f) if r.get("symbol")})
    return out


US_UNIVERSE: list[str] = _load_sp500() or _FALLBACK_US

# --- IDX (Fase 3): LQ45 — saham paling likuid di BEI (suffix .JK utk yfinance) ---
IDX_UNIVERSE: list[str] = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK", "ASII.JK", "UNVR.JK",
    "ICBP.JK", "INDF.JK", "GGRM.JK", "HMSP.JK", "KLBF.JK", "ANTM.JK", "ADRO.JK",
    "PGAS.JK", "PTBA.JK", "SMGR.JK", "UNTR.JK", "GOTO.JK", "BUKA.JK", "ARTO.JK",
    "MDKA.JK", "INCO.JK", "TPIA.JK", "AMRT.JK", "CPIN.JK", "TOWR.JK", "TBIG.JK",
    "EXCL.JK", "ISAT.JK", "AKRA.JK", "BRPT.JK", "MEDC.JK", "ITMG.JK", "INKP.JK",
    "BSDE.JK", "CTRA.JK", "PWON.JK", "ACES.JK", "ERAA.JK", "JPFA.JK", "MNCN.JK",
    "ADMR.JK", "INDY.JK", "MAPI.JK",
]


def all_symbols() -> list[str]:
    """Gabungan universe aktif. IDX kosong sampai Fase 3."""
    return US_UNIVERSE + IDX_UNIVERSE


def market_of(symbol: str) -> str:
    """Kembalikan 'IDX' jika simbol berakhiran .JK, selain itu 'US'."""
    return "IDX" if symbol.upper().endswith(".JK") else "US"
