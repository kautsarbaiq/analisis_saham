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

    Strategi: DELETE baris yang key-nya muncul di df, lalu INSERT BY NAME.
    Dijalankan dalam transaksi agar atomic. Kolom df yang tidak ada di tabel
    diabaikan; kolom tabel yang tidak ada di df diisi NULL/default (INSERT BY NAME).

    Kembalikan jumlah baris yang ditulis.
    """
    if df is None or len(df) == 0:
        return 0

    con.register("_upsert_src", df)
    try:
        con.execute("BEGIN")
        # Hapus baris lama dengan key yang sama (idempotency).
        match = " AND ".join(f"t.{k} = s.{k}" for k in key_cols)
        con.execute(
            f"DELETE FROM {table} AS t "
            f"WHERE EXISTS (SELECT 1 FROM _upsert_src AS s WHERE {match})"
        )
        # Sisipkan data baru; cocokkan kolom berdasarkan nama.
        con.execute(f"INSERT INTO {table} BY NAME SELECT * FROM _upsert_src")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("_upsert_src")

    return len(df)
