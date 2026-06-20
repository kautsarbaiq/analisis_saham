"""Entry-point batch harian US (dijalankan GitHub Actions ~04:00 WIB).

Orkestrasi end-to-end (lihat docs/01_architecture.md):
  ingest -> features -> engines -> composite -> event-study -> simpan.
Harus IDEMPOTENT: aman dijalankan ulang untuk tanggal yang sama.
"""
from __future__ import annotations


def run() -> None:
    """Jalankan pipeline harian US.

    TODO(impl, Fase 0-2):
      1. storage.db.connect() + init_schema()
      2. ingestion.prices.fetch(US_UNIVERSE) -> upsert
      3. ingestion.fundamentals.fetch(...) -> upsert         (Fase 1)
      4. ingestion.news.fetch(...) -> upsert                 (Fase 2)
      5. features.technical/fundamental.compute(...) -> upsert
      6. engines.*.score(...) -> engine_scores
      7. scoring.composite.combine(...) -> composite_scores
      8. engines.event_study.evaluate(...) -> predictions    (Fase 2)
    """
    raise NotImplementedError("Implementasi bertahap Fase 0-2.")


if __name__ == "__main__":
    run()
