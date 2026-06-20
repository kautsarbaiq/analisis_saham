"""Evaluasi akurasi prediksi (akuntabilitas berjalan).

Untuk tiap prediksi yang horizon-nya sudah lewat, hitung realized_return & was_correct,
update tabel `predictions`. Inilah sumber halaman Track Record yang jujur.
"""
from __future__ import annotations


def run() -> None:
    """Cek prediksi jatuh tempo -> isi realized_return & was_correct.

    TODO(impl, Fase 2):
      1. ambil predictions dgn realized_return IS NULL dan asof+horizon <= hari ini.
      2. hitung return aktual dari `prices`.
      3. was_correct = (arah aktual sesuai prob_up>50%).
      4. update; agregat akurasi per tipe event untuk dashboard.
    """
    raise NotImplementedError("Implementasi di Fase 2.")


if __name__ == "__main__":
    run()
