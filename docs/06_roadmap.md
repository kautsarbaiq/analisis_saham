# 06 — Roadmap Bertahap & KPI Terukur

Setiap fase punya **definition of done yang terukur** — bukan "selesai" karena fitur ada,
tapi karena terbukti bekerja lewat angka.

## Fase 0 — Fondasi
**Bangun:** struktur proyek, DuckDB + skema, ingestion harga US, scheduler GitHub Actions.
**DoD terukur:** universe US (15→500 saham) ter-update otomatis tiap hari tanpa error;
data lolos validasi kualitas (tak ada harga ≤ 0, gap tanggal tertangani).

## Fase 1 — Otak Analitik US
**Bangun:** fundamental engine (SEC EDGAR), technical engine, backtest engine,
composite score, dashboard Streamlit, screener harian.
**DoD terukur:**
- Quantile backtest: portofolio skor-tinggi **outperform** skor-rendah secara
  signifikan (mis. selisih CAGR positif, Sharpe lebih baik) *out-of-sample*.
- Dashboard menampilkan skor + breakdown + N + confidence untuk tiap saham.

## Fase 2 — News Engine + Alert
**Bangun:** ingestion berita (GDELT/RSS), klasifikasi event (Groq), FinBERT sentimen,
event-study engine, alert Telegram, halaman Track Record.
**DoD terukur:**
- Classifier event: precision/recall ≥ baseline yang ditetapkan (mis. ≥0.7 pada set uji).
- Event-study mengeluarkan forecast dengan N & CI; guardrail low-confidence aktif.
- Prediksi mulai dicatat & dievaluasi otomatis.

## Fase 3 — Port ke IDX + Bandarmology Proxy
**Bangun:** ingestion IDX (.JK), bandarmology proxy (foreign flow, akum/dist),
adaptasi semua engine ke konteks IDX.
**DoD terukur:**
- Proxy bandarmology punya win-rate **> random (50%)** secara terukur & signifikan;
  jika tidak, ditandai "belum tervalidasi, bobot 0".

## Fase 4 — Laporan Riset Otomatis
**Bangun:** generator laporan naratif (Gemini) yang merangkai ANGKA dari engine
menjadi tesis/valuasi/risiko/katalis ala analis.
**DoD terukur:**
- Audit konsistensi: setiap klaim angka di laporan **cocok** dengan tabel engine
  (uji otomatis anti-halusinasi LLM); 0 angka mengarang pada sampel uji.

## Fase 5 — Komersialisasi
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
