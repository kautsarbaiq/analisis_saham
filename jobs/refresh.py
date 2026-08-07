"""Refresh harian RINGAN (untuk scheduler: launchd/cron/GitHub Actions).

Hanya tarik harga terbaru (period pendek -> upsert; histori lama tetap) lalu
re-score. TIDAK menarik fundamental SEC tiap hari (cukup mingguan; sudah di DB).
Backtest 5 tahun dijalankan terpisah/sesekali, bukan harian.

Jalan: ~1-2 menit untuk 503 simbol.
"""
from __future__ import annotations

from jobs.daily_us import run


def main() -> None:
    # Update short volume FINRA (resumable — hanya tarik hari yg belum ada, cepat).
    try:
        from jobs import shortvol_ingest
        shortvol_ingest.run()
    except Exception as exc:  # noqa: BLE001 — jangan gugurkan refresh krn sumber eksternal
        print(f"[refresh] shortvol_ingest dilewati: {exc}")
    # period pendek: cukup untuk update harga terbaru & isi gap; scoring memakai
    # seluruh histori yang sudah ada di DB.
    run(period="1mo", with_fundamentals=False)

    # Digest berita portofolio (butuh skor terbaru -> dijalankan SETELAH scoring).
    # Sekaligus mengarsipkan headline ke tabel `news` agar lapisan berita bisa
    # divonis nanti (jobs/news_forward_test.py).
    try:
        from jobs import news_digest
        news_digest.run()
    except Exception as exc:  # noqa: BLE001 — RSS eksternal, jangan gugurkan refresh
        print(f"[refresh] news_digest dilewati: {exc}")


if __name__ == "__main__":
    main()
