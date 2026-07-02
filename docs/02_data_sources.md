# 02 — Sumber Data, Lisensi, & Batas

> Aturan emas: data yang **gratis untuk pribadi** sering **ILEGAL untuk dijual ulang**.
> Kolom "Boleh dijual?" di bawah menentukan apa yang harus di-swap di Fase 5.

## Saham US

| Data | Sumber (free) | Kualitas | Boleh dijual ulang? | Catatan |
|---|---|---|---|---|
| Harga EOD | `yfinance`, Stooq | Tinggi | ⚠️ ToS abu-abu | Untuk produk: swap ke Polygon/Tiingo berlisensi |
| Harga intraday | `yfinance` (15m delay) | Sedang | ❌ | Real-time butuh data berbayar |
| Fundamental | **SEC EDGAR API** | Institusional | ✅ **Public domain** | Sumber resmi; aman dijual |
| Insider (SEC Form 4 / bulk Form 345) | **SEC EDGAR** | Institusional | ✅ **Public domain** | Aman komersial. Bulk kuartalan (lag ~1 kuartal) + real-time per emiten (Form 4 XML) — `src/ingestion/insider.py` |
| Makro | **FRED API** | Institusional | ✅ | Wajib atribusi |
| Estimasi analis | — | — | ❌ | Tidak ada sumber gratis bersih |

> **SEC EDGAR adalah permata gratis Anda**: laporan 10-K/10-Q/8-K resmi, public domain,
> boleh dipakai komersial. Inti "analisis ala huge fund" untuk fundamental berasal dari sini.

## Saham IDX

| Data | Sumber (free) | Kualitas | Boleh dijual ulang? | Catatan |
|---|---|---|---|---|
| Harga EOD | `yfinance` (`.JK`), scraping IDX | Sedang | ❌ | Validasi silang karena kadang ada gap |
| Fundamental | scraping laporan IDX/IDN Financials | Rendah-sedang | ❌ | Manual/scraping, perlu pembersihan |
| **Broker summary (bandarmology asli)** | **TIDAK ADA gratis-bersih** | — | ❌ | **Blocker.** Premium: Stockbit/RTI/IDX feed |
| Foreign flow (proxy bandar) | scraping/agregasi publik | Sedang | ⚠️ | Dipakai sebagai PROXY di Fase 3 |

> **Bandarmology asli = satu-satunya fitur yang benar-benar terhalang budget $0.**
> Mitigasi terukur: pakai *proxy* (foreign net flow, akumulasi/distribusi via volume)
> dengan win-rate yang diukur jujur, dan tandai sebagai "Tier-2: butuh upgrade data".

## Berita

| Sumber | Cakupan | Boleh dijual? | Catatan |
|---|---|---|---|
| **GDELT** | Global, event ter-struktur, historis | ✅ (cek ToS) | DB event raksasa GRATIS; ideal untuk event-study historis |
| RSS (Reuters, CNBC, Kontan, Bisnis, IDX) | Headline real-time | ⚠️ (headline only) | `feedparser`; simpan link, bukan full text |
| NewsAPI (free) | 100 req/hari | ❌ (free tier) | Untuk MVP pribadi saja |

## LLM (klasifikasi event & laporan)

| Layanan | Free-tier | Pakai untuk |
|---|---|---|
| Groq (Llama) | Generous, cepat | Klasifikasi tipe event berita (volume tinggi) |
| Gemini | Free-tier harian | Laporan riset naratif (Fase 4) |
| FinBERT (lokal) | Gratis penuh | Skor sentimen finansial (tanpa API) |
| VADER (lokal) | Gratis penuh | Baseline sentimen cepat |

## Kebijakan kualitas data (wajib di `ingestion/`)

1. **Validasi**: tolak harga ≤ 0, deteksi gap tanggal, tandai stock split/dividen.
2. **Survivorship bias**: catat saham yang delisting; backtest yang mengabaikan ini
   akan terlihat lebih bagus dari kenyataan (lihat [05_backtesting.md](05_backtesting.md)).
3. **Timestamp jujur**: simpan kapan data *tersedia*, bukan kapan *terjadi*
   (hindari look-ahead bias pada berita & fundamental).
4. **Rate-limit sopan**: jeda `REQUEST_DELAY_SEC` antar request ke API gratis.
