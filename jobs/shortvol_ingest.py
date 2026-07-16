"""Ingest FINRA daily short volume (5 th, universe US) ke tabel short_volume.

Audit dari kegagalan sebelumnya: inkremental PER BULAN + resumable — kill di
tengah hanya kehilangan <=1 bulan, jalankan lagi utk melanjutkan. Upsert
idempotent per bulan.

Audit fix (multi-agent):
- Kunci skip = (tahun, bulan) penuh; dulu hanya NOMOR bulan (ms.month) sehingga
  semua bulan bernomor sama di tahun lampau di-download ulang tiap run.
- "Sudah lengkap" kini diukur dari jumlah HARI berbeda vs hari kerja bulan tsb
  (toleransi 3 utk libur bursa); dulu bulan yang baru terisi 1 hari (fetch mati
  di tengah) dianggap lengkap selamanya.
- run(force=True): abaikan skip, tarik ulang semuanya — dipakai utk backfill
  (mis. setelah fix simbologi BRK/B -> BRK-B).
"""
from __future__ import annotations

from datetime import date, timedelta

from config.universe import US_UNIVERSE
from src.ingestion.short_volume import fetch_range
from src.storage import db

START = date(2021, 6, 21)  # selaras dgn histori harga


def _month_starts(start: date, end: date):
    d = start.replace(day=1)
    while d <= end:
        yield d
        d = (d.replace(day=28) + timedelta(days=7)).replace(day=1)


def _weekdays(lo: date, hi: date) -> int:
    n, d = 0, lo
    while d <= hi:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def month_complete(days_present: int, lo: date, hi: date) -> bool:
    """Bulan dianggap lengkap bila jumlah hari data >= hari kerja - 3 (libur bursa)."""
    return days_present >= _weekdays(lo, hi) - 3


def run(force: bool = False) -> None:
    con = db.connect(); db.init_schema(con)
    uni = set(US_UNIVERSE)
    # File FINRA hari-D terbit ~malam D waktu ET — file "hari ini" hampir pasti
    # belum ada (CDN menjawab 403 dan retry backoff membuang ~18 dtk). Tarik
    # sampai kemarin saja; engine pun hanya butuh data < as_of (lag-1).
    today = date.today() - timedelta(days=1)

    have: dict[str, int] = dict(con.execute(
        "SELECT strftime(date, '%Y-%m'), count(DISTINCT date) "
        "FROM short_volume GROUP BY 1").fetchall())

    total = 0
    for ms in _month_starts(START, today):
        tag = ms.strftime("%Y-%m")
        me = (ms.replace(day=28) + timedelta(days=7)).replace(day=1) - timedelta(days=1)
        lo, hi = max(ms, START), min(me, today)
        current = (ms.year, ms.month) == (today.year, today.month)
        if not force and not current and month_complete(have.get(tag, 0), lo, hi):
            continue
        df = fetch_range(lo, hi, uni)
        if not df.empty:
            n = db.upsert_df(con, "short_volume", df, ["symbol", "date"])
            total += n
            print(f"[shortvol] {tag}: +{n} baris (kumulatif {total})")

    r = con.execute("SELECT count(*), count(DISTINCT symbol), min(date), max(date) "
                    "FROM short_volume").fetchone()
    print(f"[shortvol] SELESAI. DB: {r[0]} baris, {r[1]} simbol, {r[2]}..{r[3]}")
    con.close()


if __name__ == "__main__":
    import sys
    run(force="--force" in sys.argv)
