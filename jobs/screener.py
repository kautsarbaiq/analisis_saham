"""Screener harian (dijalankan setelah daily_us.py).

Ranking composite_scores -> "Top N setup hari ini" dengan alasan terukur tiap masuk
daftar, lalu kirim ke Telegram. Output netral & probabilistik (bukan "BELI").
"""
from __future__ import annotations


def run(top_n: int = 10) -> None:
    """Ambil composite_scores terbaru, ranking, kirim Top N ke Telegram.

    TODO(impl, Fase 1):
      1. query composite_scores utk asof terbaru.
      2. filter confidence != 'low' (atau tandai jelas).
      3. urutkan; sertakan breakdown + prediksi terukur per saham.
      4. delivery.alerts.send(format ringkas + disclaimer).
    """
    raise NotImplementedError("Implementasi di Fase 1.")


if __name__ == "__main__":
    run()
