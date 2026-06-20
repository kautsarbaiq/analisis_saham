"""Koneksi & helper DuckDB.

Satu-satunya pintu ke storage. Engine lain TIDAK boleh membuka koneksi sendiri —
agar skema, migrasi, dan idempotency terpusat di sini.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from config import settings


def connect() -> "duckdb.DuckDBPyConnection":
    """Buka koneksi DuckDB ke DUCKDB_PATH (buat folder bila perlu)."""
    Path(settings.DUCKDB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(settings.DUCKDB_PATH)


def init_schema(con: "duckdb.DuckDBPyConnection") -> None:
    """Jalankan schema.sql (idempotent — CREATE TABLE IF NOT EXISTS)."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    con.execute(sql)


def upsert_df(con, table: str, df, key_cols: list[str]) -> int:
    """UPSERT DataFrame ke `table` berdasarkan key_cols (idempotent).

    TODO(impl): DELETE baris dengan key yang sama lalu INSERT, atau pakai
    MERGE/ON CONFLICT. Kembalikan jumlah baris ter-update.
    """
    raise NotImplementedError("Implementasi di Fase 0.")
