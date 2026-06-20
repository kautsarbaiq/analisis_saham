"""Ingestion fundamental dari SEC EDGAR (US).

SEC EDGAR = sumber resmi, public domain, AMAN untuk komersial. Wajib kirim header
User-Agent berisi email (settings.SEC_USER_AGENT) sesuai aturan SEC.

Anti look-ahead: simpan `filed_at` (kapan laporan dirilis), bukan hanya `period`.
Backtest hanya boleh memakai fundamental yang sudah `filed_at <= asof`.
"""
from __future__ import annotations


def fetch(symbols: list[str]):
    """Ambil fakta XBRL (companyfacts API) -> baris (symbol, period, metric, value, filed_at).

    TODO(impl, Fase 1):
      1. Resolve ticker -> CIK (pakai daftar CIK SEC).
      2. GET data.sec.gov/api/xbrl/companyfacts/CIK{...}.json (header User-Agent).
      3. Ekstrak metrik kunci: Revenues, NetIncomeLoss, Assets, Liabilities,
         StockholdersEquity, EPS, OperatingIncomeLoss, dst.
      4. Catat filed_at dari tiap fact (kunci anti look-ahead).
    """
    raise NotImplementedError("Implementasi di Fase 1.")
