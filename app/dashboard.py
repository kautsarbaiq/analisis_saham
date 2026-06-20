"""Dashboard Streamlit (Lapisan 7).

Membaca dari DuckDB (tidak menghitung apa pun — semua sudah dihitung batch job).
Halaman:
  1. Overview      : ranking composite score + filter pasar/sektor.
  2. Detail Saham  : breakdown engine, prediksi event-study (P, CI, N), grafik harga.
  3. Screener      : Top setup hari ini.
  4. Track Record  : akurasi sistem berjalan (JUJUR — termasuk yang salah).

Semua output netral & probabilistik + disclaimer compliance (07_compliance.md).
"""
from __future__ import annotations

# TODO(impl, Fase 1):
#   import streamlit as st
#   con = storage.db.connect()
#   - st.dataframe(composite_scores) dengan kolom skor + confidence
#   - halaman detail: components per engine, predictions, grafik plotly
#   - halaman track record: win-rate aktual + Wilson CI per tipe event
#
# Jalankan: streamlit run app/dashboard.py

def main() -> None:
    raise NotImplementedError("Implementasi di Fase 1.")


if __name__ == "__main__":
    main()
