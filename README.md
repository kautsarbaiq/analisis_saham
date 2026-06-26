# 🏛️ Project Bandar — Platform Analisis Saham US & IDX

> Mesin analisis saham probabilistik & terukur — fundamental, teknikal, sentimen berita
> (event-study), dan bandarmology — dengan backtesting jujur dan track-record yang
> menelanjangi akurasinya sendiri.

**Status:** `Fase 0 — Cetak biru (skeleton + dokumen teknis). Belum ada implementasi logika.`

---

## Prinsip non-negosiasi

1. **Tidak ada opini tanpa data terukur.** Setiap sinyal wajib ter-backtest dengan
   sample size (N), win-rate, dan confidence interval. Jika N terlalu kecil → sistem
   WAJIB menyatakan *low confidence*, bukan mengarang.
2. **Output selalu probabilistik.** Bukan "akan naik" tapi
   "probabilitas 62% (CI 55–69%), N=312".
3. **Sistem menilai dirinya sendiri.** Setiap prediksi disimpan dan dicek hasil
   aktualnya → halaman Track Record menampilkan akurasi berjalan.
4. **Pemisahan Data Layer.** Versi pribadi memakai sumber gratis; versi komersial
   tinggal swap ke sumber berlisensi tanpa mengubah engine.
5. **Positioning: alat analisis & edukasi, BUKAN nasihat beli/jual.** (lihat
   [docs/07_compliance.md](docs/07_compliance.md))

> ⚠️ **Batas jujur (terukur):** target realistis win-rate ~52–60%. Sebagai pembanding,
> fund kuantitatif terbaik dalam sejarah (Renaissance Medallion) menang ~50,75% per
> transaksi. "Menebak tepat" secara matematis mustahil; yang dibangun di sini adalah
> *edge tipis yang konsisten dan terukur*.

---

## Arsitektur 7 Lapisan

```
7. DELIVERY      Dashboard · Screener · Alert · Auto-Report
6. SCORING       Composite Score + Probabilistic Forecast (+ CI)
5. ENGINES       Fundamental · Technical · Sentiment/News · Bandarmology · Quant
4. BACKTEST      Validasi tiap sinyal sebelum tayang (anti-overfitting)
3. FEATURES      Feature store: indikator terhitung, di-cache, reusable
2. STORAGE       DuckDB (analitik/backtest) + Postgres (app state)
1. INGESTION     Scheduler (GitHub Actions) → tarik & bersihkan data
```

Detail: [docs/01_architecture.md](docs/01_architecture.md)

---

## Tech Stack (di-tuning untuk $0–$20/bulan)

| Lapisan | Pilihan |
|---|---|
| Bahasa engine | Python 3.11 |
| Harga US/IDX | `yfinance`, Stooq |
| Fundamental US | SEC EDGAR API |
| Makro | FRED API |
| Berita | GDELT, RSS (`feedparser`), NewsAPI free |
| NLP sentimen | FinBERT / VADER (lokal) + Groq/Gemini free-tier |
| Database | DuckDB + Supabase Postgres (free) |
| Scheduler | GitHub Actions (cron gratis) |
| Dashboard | Streamlit (Streamlit Cloud free) |
| Alert | Telegram Bot API |

Detail + lisensi: [docs/02_data_sources.md](docs/02_data_sources.md)

---

## Struktur Direktori

```
analisis_saham/
├── README.md                 ← Anda di sini
├── requirements.txt
├── .env.example              ← template API keys (salin ke .env)
├── config/                   ← konfigurasi & daftar saham (universe)
├── docs/                     ← 7 dokumen teknis (CETAK BIRU)
├── src/
│   ├── ingestion/            ← Lapisan 1: tarik data
│   ├── storage/              ← Lapisan 2: DuckDB + skema
│   ├── features/             ← Lapisan 3: feature store
│   ├── engines/              ← Lapisan 5: 5 engine analitis
│   ├── scoring/              ← Lapisan 6: composite score
│   ├── backtest/             ← Lapisan 4: backtesting + metrik
│   ├── nlp/                  ← klasifikasi event + sentimen
│   └── delivery/             ← Lapisan 7: alert + laporan
├── app/                      ← dashboard Streamlit
├── jobs/                     ← entry-point untuk scheduler
├── .github/workflows/        ← cron GitHub Actions
└── tests/
```

---

## Roadmap (bertahap / tiered)

| Fase | Isi | KPI terukur |
|---|---|---|
| **0** | Fondasi: pipeline data US + DuckDB + scheduler | 500 saham US ter-update otomatis |
| **1** | Engine fundamental+teknikal + backtest + dashboard + screener | Quantile-backtest: skor-tinggi outperform skor-rendah |
| **2** | News event-study engine + alert Telegram + track-record | Precision/recall classifier ≥ baseline |
| **3** | Port ke IDX + bandarmology proxy | Win-rate proxy bandar > random (terukur) |
| **4** | Laporan riset otomatis (LLM) | Laporan konsisten dengan angka engine |
| **5** | Komersialisasi: data berlisensi + auth + billing + compliance | Siap jual, track record publik |

Detail + definisi KPI: [docs/06_roadmap.md](docs/06_roadmap.md)

---

## Cara Menjalankan

```bash
uv venv --python 3.12 .venv          # atau: python -m venv .venv
uv pip install --python .venv -r requirements.txt
python -m jobs.daily_us              # tarik harga+SEC, hitung skor (~12 mnt, 503 saham)
python -m jobs.backtest_mean_reversion   # validasi engine (sesekali)
python -m jobs.backtest_factor score_below_ma mean_reversion 5,10
.venv/bin/uvicorn app.server:app --port 8000    # dashboard -> http://localhost:8000
```

Refresh harian ringan (harga + skor saja, ~1–2 mnt): `python -m jobs.refresh`

## Otomatisasi

**Lokal (macOS, langsung berguna):** jalankan refresh tiap pagi via launchd —
```bash
cp scripts/com.projectbandar.daily.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.projectbandar.daily.plist   # bongkar: launchctl unload ...
```

**Cloud (GitHub Actions, $0):** `.github/workflows/daily_us.yml` menarik harga segar,
skor pakai vonis backtest statis [`config/validation.json`](config/validation.json),
lalu commit [`snapshots/latest.json`](snapshots/latest.json) balik ke repo (rekam jejak
harian + sumber dashboard hosted). Aktif begitu repo di-push ke GitHub. Backtest 5 tahun
dijalankan terpisah (bukan harian) karena butuh histori penuh.
