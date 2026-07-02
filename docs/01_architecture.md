# 01 — Arsitektur Sistem

## Tujuan desain

Sistem harus: (a) jalan di **$0–$20/bulan**, (b) tidak butuh server nyala 24 jam,
(c) reproducible (backtest hari ini = backtest besok untuk data yang sama),
(d) modular agar tiap engine bisa dikembangkan & di-backtest terpisah.

Solusinya: **arsitektur batch-first.** Hampir semua komputasi dijalankan sebagai
*scheduled job* (GitHub Actions, gratis), menulis hasil ke database, lalu frontend
hanya membaca. Tidak ada layanan real-time mahal kecuali nanti di fase upgrade.

## 7 Lapisan

```
┌─────────────────────────────────────────────────────────────┐
│ 7. DELIVERY      app/server.py + app/static/ (FastAPI,        │
│                  terminal ala Bloomberg) · jobs/screener.py ·  │
│                  src/delivery/alerts.py · report.py (stub)     │
├─────────────────────────────────────────────────────────────┤
│ 6. SCORING       src/scoring/composite.py                     │
│                  → gabung skor engine + forecast probabilistik │
├──────────────┬──────────────┬──────────────┬─────────────────┤
│ 5 ENGINES     fundamental · technical · sentiment · bandar ·  │
│               quant   (src/engines/*)                         │
├──────────────┴──────────────┴──────────────┴─────────────────┤
│ 4. BACKTEST      src/backtest/* — validasi sinyal SEBELUM     │
│                  tayang; hitung win-rate, Sharpe, CI          │
├─────────────────────────────────────────────────────────────┤
│ 3. FEATURES      src/features/* — indikator terhitung,        │
│                  di-cache di DuckDB (hindari hitung ulang)     │
├─────────────────────────────────────────────────────────────┤
│ 2. STORAGE       src/storage/* — DuckDB (analitik) + skema    │
├─────────────────────────────────────────────────────────────┤
│ 1. INGESTION     src/ingestion/* — tarik, validasi, bersihkan │
└─────────────────────────────────────────────────────────────┘
        ▲ dijalankan oleh: .github/workflows/*.yml (cron)
```

## Aliran data (daily batch — US)

Sesuai implementasi nyata `jobs/daily_us.py`:

```
GitHub Action (cron ~04:00 WIB) / launchd lokal
  └─ jobs/daily_us.py
       1. ingestion.prices.fetch_bulk(universe US+IDX)        → tabel prices (upsert)
       2. ingestion.fundamentals.fetch(simbol US)  [opsional]  → tabel fundamentals (SEC EDGAR)
       3. _score_all — MARKET-AWARE, sinyal dihitung dari harga
          TER-ADJUST split/dividen (DuckDB `db.ADJ_PRICES_SQL`):
            pass 1  skor mentah per simbol: technical · mean_reversion ·
                    event_drift · insider (US-only, bulk Form 345 + cek
                    staleness) · fundamental (bila ada data SEC)
            antara  event_drift di-sector-neutralkan cross-sectional
                    PER MARKET (demean per sektor GICS utk US; grup IDX
                    terpisah) — edge-nya tervalidasi sbg alpha dalam-sektor
            pass 2  scoring.composite.combine — HANYA engine yang tervalidasi
                    utk market ybs (tabel `validation` per-market; fallback
                    config/validation.json). Tak ada engine valid → total None.
       4. upsert → tabel engine_scores + composite_scores
  └─ jobs/screener.py        → Top-N per market → delivery.alerts (Telegram, opsional)
  └─ jobs/export_snapshot.py → snapshots/latest.json (top_us/top_idx)
                               + config/validation.json (vonis per-market)
```

## Prinsip pemisahan Data Layer (kunci komersialisasi)

`src/ingestion/` adalah satu-satunya tempat yang tahu *dari mana* data berasal.
Engine di atasnya hanya bicara ke **skema tabel internal**, bukan ke sumber.
Konsekuensinya: untuk versi komersial, cukup ganti implementasi di `ingestion/`
(sumber gratis → sumber berlisensi) tanpa menyentuh engine, scoring, atau backtest.

```
[Engine & Scoring]  ── baca ──>  [Skema tabel internal]
                                        ▲ tulis
                          [ingestion/ — SATU-SATUNYA yang tahu sumber]
                          pribadi: yfinance/scraping  | jual: data berlisensi
```

## Kenapa DuckDB (bukan langsung Postgres)

- **Gratis, file-based, nol kredensial** — cocok untuk MVP pribadi.
- **Sangat cepat untuk query analitik & backtest** (kolomnar, vektorisasi).
- Bisa baca Parquet/CSV langsung; mudah di-version di disk.
- Postgres (Supabase free) ditambahkan nanti hanya untuk *app state* multi-user
  (auth, langganan) saat Fase 5, bukan untuk analitik.

## Idempotency & reproducibility

Setiap job harus **idempotent**: dijalankan dua kali untuk tanggal sama →
hasil sama (UPSERT, bukan append buta). Ini syarat mutlak agar backtest tidak bias
dan agar job yang gagal di tengah bisa diulang dengan aman.
