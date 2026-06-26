"""Refresh harian RINGAN (untuk scheduler: launchd/cron/GitHub Actions).

Hanya tarik harga terbaru (period pendek -> upsert; histori lama tetap) lalu
re-score. TIDAK menarik fundamental SEC tiap hari (cukup mingguan; sudah di DB).
Backtest 5 tahun dijalankan terpisah/sesekali, bukan harian.

Jalan: ~1-2 menit untuk 503 simbol.
"""
from __future__ import annotations

from jobs.daily_us import run


def main() -> None:
    # period pendek: cukup untuk update harga terbaru & isi gap; scoring memakai
    # seluruh histori yang sudah ada di DB.
    run(period="1mo", with_fundamentals=False)


if __name__ == "__main__":
    main()
