# 🏛️ Project Bandar — Platform Analisis Saham US & IDX

> Mesin analisis saham probabilistik & terukur — fundamental, teknikal, sentimen berita
> (event-study), dan bandarmology — dengan backtesting jujur dan track-record yang
> menelanjangi akurasinya sendiri.

**Status:** `Fase 0-3 TERIMPLEMENTASI & diaudit (2x audit multi-agent). 2 sinyal independen tervalidasi US: shortvol_level (FINRA short volume, h21+h63 — terkuat) + event_drift (PEAD proxy, h63). Engine lain berjalan deskriptif dengan bobot composite 0 (gagal validasi rigor per-market); IDX belum ada yang lolos.`

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
| Insider | SEC Form 4 / bulk Form 345 (EDGAR, public domain) |
| Short volume harian US | FINRA Reg SHO (CDN publik, tanpa API key) |
| Makro | FRED API |
| Berita | GDELT, RSS (`feedparser`), NewsAPI free |
| NLP sentimen | FinBERT / VADER (lokal) + Groq/Gemini free-tier |
| Database | DuckDB + Supabase Postgres (free) |
| Scheduler | GitHub Actions (cron gratis) + launchd lokal |
| Dashboard | FastAPI + HTML/JS custom (terminal ala Bloomberg) |
| Alert | Telegram Bot API |

Detail + lisensi: [docs/02_data_sources.md](docs/02_data_sources.md)

---

## Struktur Direktori

```
analisis_saham/
├── README.md                 ← Anda di sini
├── requirements.txt
├── .env.example              ← template API keys (salin ke .env)
├── config/                   ← settings, universe (sp500.csv, LQ45), validation.json
├── docs/                     ← 7 dokumen teknis
├── src/
│   ├── ingestion/            ← Lapisan 1: harga, fundamental, insider, berita, GDELT
│   ├── storage/              ← Lapisan 2: DuckDB + skema (data/bandar.duckdb)
│   ├── features/             ← Lapisan 3: feature store
│   ├── engines/              ← Lapisan 5: engine analitis
│   ├── scoring/              ← Lapisan 6: composite score
│   ├── backtest/             ← Lapisan 4: backtesting + metrik
│   ├── nlp/                  ← sentimen (FinBERT/VADER); klasifikasi event = stub
│   └── delivery/             ← Lapisan 7: alert Telegram; report = stub
├── app/                      ← dashboard FastAPI: server.py + service.py + static/ (HTML/JS/CSS)
├── jobs/                     ← entry-point scheduler (daily_us, refresh, screener, backtest_*, ...)
├── snapshots/                ← latest.json (top_us/top_idx) — rekam jejak harian
├── scripts/                  ← launchd plist utk refresh pagi lokal
├── .github/workflows/        ← cron GitHub Actions (daily_us.yml, tests.yml)
└── tests/
```

---

## Roadmap (bertahap / tiered)

| Fase | Isi | Status |
|---|---|---|
| **0** | Fondasi: pipeline data US + DuckDB + scheduler | ✅ Selesai — 503 saham S&P 500, 5 th data |
| **1** | Engine fundamental+teknikal + backtest + dashboard + screener | 🟡 Selesai sebagian — semua jalan; fundamental & technical GAGAL validasi → deskriptif |
| **2** | News event-study engine + alert Telegram + track-record | 🟡 Selesai sebagian — event_drift (PEAD proxy) TERVALIDASI US h63; berita live belum di-backtest |
| **3** | Port ke IDX + bandarmology proxy | ✅ Selesai — 45 LQ45 ter-skor; NOL engine valid IDX (proxy bandar diuji & gagal) |
| **4** | Laporan riset otomatis (LLM) | ⬜ Belum |
| **5** | Komersialisasi: data berlisensi + auth + billing + compliance | ⬜ Belum |

Detail + definisi KPI: [docs/06_roadmap.md](docs/06_roadmap.md)

### Vonis validasi terkini (rigor penuh, per-market)

Setelah backtest dengan harga ter-adjust, kuantil cross-sectional per-tanggal,
walk-forward out-of-sample, dan sector-neutralization
([config/validation.json](config/validation.json)):

- **TERVALIDASI — `shortvol_level`** (FINRA daily short volume; skor `(1−SVR5)×100`,
  hipotesis a-priori, lag-1 publikasi): US sector-neutral **+0.39%/21d (t 9.8)** dan
  **+1.67%/63d (t 23.9)**; kuintil monotonik; lolos uji adversarial lag & penny-stock.
  Sinyal terkuat (bobot 0.30). `shortvol_chg` juga lolos h63 tapi sengaja tidak
  diproduksi. *Catatan: ini short VOLUME harian, bukan short INTEREST bi-mingguan.*
- **TERVALIDASI — `event_drift`** US h63 (PEAD proxy) — sector-neutral +0.56%/63d
  (t 6.4); versi raw juga lolos.
- **DITOLAK:** mean_reversion (US & IDX — edge lama ternyata artefak kuantil pooled),
  insider (t 1.25 pada uji non-overlap), fundamental, technical/momentum (edge ~0),
  low_volatility, bandarmology-proxy (justru kontrarian di IDX).
- **IDX: nol engine tervalidasi** → composite IDX sengaja kosong (jujur, bukan bug).

**Track record** ([jobs/track_record.py](jobs/track_record.py)): simulasi portofolio
composite dinamis (identik produksi — 2 sinyal tervalidasi, renormalisasi atas engine
ber-data), long-only bulanan top-20, NET 15 bps: **+125.3% vs benchmark equal-weight
+75.1%** (4.2 th, Sharpe 1.04, hit-rate 58% vs benchmark).
*Caveat: universe mengandung survivorship bias dan periode uji didominasi rezim bull —
angka ini batas atas optimis, bukan janji.*

---

## Cara Menjalankan

```bash
uv venv --python 3.12 .venv          # atau: python -m venv .venv
uv pip install --python .venv -r requirements.txt
python -m jobs.shortvol_ingest       # histori short volume FINRA (run perdana ~20 mnt; resumable)
python -m jobs.daily_us              # tarik harga+SEC, hitung skor (~12 mnt, 548 saham US+IDX)
# Validasi engine (sesekali, bukan harian — butuh histori penuh):
python -m jobs.backtest_factor event_drift_score event_drift 21,63 US
python -m jobs.backtest_shortvol     # vonis short-volume (hipotesis a-priori)
python -m jobs.backtest_idx          # vonis per-market IDX
python -m jobs.track_record          # simulasi portofolio (composite = engine tervalidasi)
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
