# 06 — Roadmap Bertahap & KPI Terukur

Setiap fase punya **definition of done yang terukur** — bukan "selesai" karena fitur ada,
tapi karena terbukti bekerja lewat angka.

## Pelajaran terukur (status per Fase 0–3)

Mayoritas "edge" yang awalnya terlihat **menguap begitu rigor dinaikkan**: harga
ter-adjust split/dividen, kuantil cross-sectional per-tanggal (bukan pooled),
walk-forward out-of-sample, sector-neutralization, dan uji non-overlap. Yang tersisa
setelah semua saringan itu hanya **satu**: `event_drift` US h63 (PEAD proxy). Ini
bukan kegagalan proses — justru inilah gunanya Lapisan 4: engine yang gagal tetap
tampil deskriptif dengan bobot composite 0, dan IDX yang belum punya engine valid
menghasilkan composite kosong secara jujur.

## Fase 0 — Fondasi ✅ SELESAI
**Bangun:** struktur proyek, DuckDB + skema, ingestion harga US, scheduler GitHub Actions.
**DoD terukur:** universe US (15→500 saham) ter-update otomatis tiap hari tanpa error;
data lolos validasi kualitas (tak ada harga ≤ 0, gap tanggal tertangani).
**Realisasi:** 503 saham S&P 500 (`config/sp500.csv`), 5 tahun data di
`data/bandar.duckdb`, cron `.github/workflows/daily_us.yml` + launchd lokal.

## Fase 1 — Otak Analitik US 🟡 SELESAI SEBAGIAN
**Bangun:** fundamental engine (SEC EDGAR), technical engine, backtest engine,
composite score, dashboard (FastAPI + HTML/JS custom), screener harian.
**DoD terukur:**
- Quantile backtest: portofolio skor-tinggi **outperform** skor-rendah secara
  signifikan (mis. selisih CAGR positif, Sharpe lebih baik) *out-of-sample*.
- Dashboard menampilkan skor + breakdown + N + confidence untuk tiap saham.

**Realisasi:** semua komponen berjalan; tapi fundamental & technical **gagal DoD
kuantitatifnya** (tidak lolos backtest sector-neutral/per-tanggal) → keduanya
deskriptif, bobot composite 0.

## Fase 2 — News Engine + Alert 🟡 SELESAI SEBAGIAN
**Bangun:** ingestion berita (GDELT/RSS), klasifikasi event (Groq), FinBERT sentimen,
event-study engine, alert Telegram, halaman Track Record.
**DoD terukur:**
- Classifier event: precision/recall ≥ baseline yang ditetapkan (mis. ≥0.7 pada set uji).
- Event-study mengeluarkan forecast dengan N & CI; guardrail low-confidence aktif.
- Prediksi mulai dicatat & dievaluasi otomatis.

**Realisasi:** event-study **proxy** (`event_drift`, PEAD dari gap harga+volume)
TERVALIDASI US h63 — satu-satunya engine lolos. Berita live (Yahoo RSS + FinBERT)
tayang deskriptif tapi **belum di-backtest**; classifier event (`nlp/classify.py`)
dan `event_study.evaluate()` masih stub. Track record composite berjalan
(`jobs/track_record.py`).

## Fase 3 — Port ke IDX + Bandarmology Proxy ✅ SELESAI (hasil: nol engine valid IDX)
**Bangun:** ingestion IDX (.JK), bandarmology proxy (foreign flow, akum/dist),
adaptasi semua engine ke konteks IDX.
**DoD terukur:**
- Proxy bandarmology punya win-rate **> random (50%)** secara terukur & signifikan;
  jika tidak, ditandai "belum tervalidasi, bobot 0".

**Realisasi:** 45 saham LQ45 ter-skor harian, vonis per-market di tabel `validation`.
Proxy bandarmology (Chaikin A/D) **diuji & GAGAL — kontrarian di IDX** → sesuai DoD,
ditandai tidak tervalidasi, bobot 0. Tidak ada engine valid IDX → composite IDX
kosong (jujur).

## Fase 4 — Laporan Riset Otomatis ⬜ BELUM
**Bangun:** generator laporan naratif (Gemini) yang merangkai ANGKA dari engine
menjadi tesis/valuasi/risiko/katalis ala analis.
**DoD terukur:**
- Audit konsistensi: setiap klaim angka di laporan **cocok** dengan tabel engine
  (uji otomatis anti-halusinasi LLM); 0 angka mengarang pada sampel uji.

## Fase 5 — Komersialisasi ⬜ BELUM
**Bangun:** swap data layer ke sumber berlisensi, auth + billing, disclaimer compliance,
landing page, halaman Track Record publik.
**DoD terukur:**
- Semua data di versi berbayar punya lisensi redistribusi sah.
- Disclaimer "alat analisis, bukan nasihat investasi" tampil & disetujui user.
- Track record publik berjalan ≥ 1 kuartal sebelum klaim performa apa pun.

## Urutan prioritas output (sesuai permintaan: keempatnya)

1. **Dashboard skor** (Fase 1) — fondasi semua.
2. **Screener harian** (Fase 1) — turunan murah dari skor.
3. **Alert real-time** (Fase 2) — butuh news engine dulu.
4. **Laporan riset otomatis** (Fase 4) — paling berat, terakhir.
