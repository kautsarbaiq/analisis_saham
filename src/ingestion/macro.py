"""Ingestion data makro dari FRED (gratis, butuh FRED_API_KEY).

Dipakai untuk regime detection & konteks event-study (mis. reaksi berita berbeda saat
suku bunga naik vs turun).

Seri awal yang relevan: DGS10 (yield 10y), VIXCLS (volatilitas), FEDFUNDS, CPIAUCSL,
UNRATE, T10Y2Y (term spread / sinyal resesi).
"""
from __future__ import annotations


def fetch(series_ids: list[str] | None = None):
    """Tarik time series makro dari FRED.

    TODO(impl, Fase 1): pandas_datareader.DataReader(series_id, 'fred', api_key=...).
    """
    raise NotImplementedError("Implementasi di Fase 1.")
