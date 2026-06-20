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
│ 7. DELIVERY      app/dashboard.py · jobs/screener.py ·        │
│                  src/delivery/alerts.py · report.py           │
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

```
GitHub Action (cron 04:00 WIB)
  └─ jobs/daily_us.py
       1. ingestion.prices.fetch(US_UNIVERSE)      → tabel prices
       2. ingestion.fundamentals.fetch(...)         → tabel fundamentals
       3. ingestion.news.fetch(...)                 → tabel news
       4. features.technical.compute(...)           → tabel features
       5. features.fundamental.compute(...)         → tabel features
       6. engines.* .score(...)                     → tabel engine_scores
       7. scoring.composite.combine(...)            → tabel composite_scores
       8. engines.event_study.evaluate(news)        → tabel predictions
  └─ jobs/screener.py → ranking → delivery.alerts (Telegram "Top N")
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
