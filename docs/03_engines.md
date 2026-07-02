# 03 — Spesifikasi Engine Analitis

Setiap engine menghasilkan **skor 0–100** (lebih tinggi = lebih bullish) PLUS
metadata terukur (komponen pembentuk skor, sample size bila relevan). Skor mentah
tidak pernah ditampilkan sebagai "rekomendasi" — ia masuk ke Lapisan 6 dan WAJIB
sudah lewat backtest sebelum dipercaya.

## Roster & status terkini (setelah validasi rigor per-market)

| Engine | File | Status |
|---|---|---|
| Event drift (PEAD proxy) | `src/engines/event_study.py` (fungsi `score`) | ✅ **TERVALIDASI** — US h63, satu-satunya |
| Technical / momentum | `src/engines/technical_engine.py` | ❌ Ditolak (edge ~0) — deskriptif |
| Mean reversion | `src/engines/mean_reversion_engine.py` | ❌ Ditolak US & IDX (edge lama = artefak kuantil pooled) — deskriptif |
| Insider | `src/engines/insider_engine.py` | ❌ Ditolak (t 1.25 non-overlap) — tetap tampil sbg info |
| Fundamental | `src/engines/fundamental_engine.py` | ❌ Ditolak sector-neutral — deskriptif |
| Bandarmology proxy | `src/engines/bandarmology_engine.py` | ❌ Diuji & GAGAL (kontrarian di IDX) — deskriptif |
| Sentiment kontinu | `src/engines/sentiment_engine.py` | 🚧 STUB |

Engine yang ditolak tetap dihitung & ditampilkan (transparansi), tapi **bobotnya di
composite = 0**. Vonis per-market tersimpan di tabel `validation` +
[config/validation.json](../config/validation.json).

---

## 5a. Fundamental Engine (`src/engines/fundamental_engine.py`) — DITOLAK, deskriptif

**Input:** tabel `fundamentals` (dari SEC EDGAR).
**Output:** skor fundamental + breakdown.

Komponen terukur:
- **Valuasi**: P/E, P/B, P/S, EV/EBITDA vs median sektor; DCF sederhana (opsional).
- **Kualitas**: ROE, ROIC, gross/operating margin + tren-nya.
- **Kesehatan**: **Altman Z-Score** (risiko kebangkrutan), current ratio, debt/equity.
- **Kekuatan akrual/akuntansi**: **Piotroski F-Score** (0–9).
- **Pertumbuhan**: CAGR revenue & EPS 3–5 tahun.

> **Vonis:** quantile backtest sector-neutral GAGAL (pooled -0.07%, t -0.34) —
> edge raw sebelumnya kemungkinan sebagian taruhan sektor. Bobot composite 0;
> tampil sebagai informasi deskriptif.

---

## 5b. Technical Engine (`src/engines/technical_engine.py`) — DITOLAK, deskriptif

**Input:** tabel `prices` (ter-adjust) + fitur indikator.
**Output:** skor teknikal + sinyal aktif.

Komponen: tren (MA stack, ADX), momentum (RSI, MACD), volatilitas (ATR, Bollinger),
volume (OBV, volume spike), level (support/resistance, breakout).

> **Vonis:** spread kuantil ~0 (h5 +0.02% t 0.69; h21 0.00) — momentum teknikal
> TIDAK punya edge terukur di universe & periode uji (bukan pula kontrarian).
> Bobot composite 0.

---

## 5b-bis. Mean Reversion Engine (`src/engines/mean_reversion_engine.py`) — DITOLAK

Skor jarak harga terhadap MA (oversold → skor tinggi).

> **Vonis:** "edge" yang dulu terlihat ternyata **artefak metodologi** — kuantil
> pooled lintas-tanggal. Setelah kuantil cross-sectional per-tanggal + walk-forward:
> US h5/h10 negatif; IDX tidak konsisten antar periode OOS. Ditolak di kedua market.

---

## 5c. Sentiment / News / Event

Tiga sub-modul dengan status berbeda:

1. **Event drift** (`event_study.py`, fungsi `score`) — ✅ TERVALIDASI. Lihat subbab
   di bawah.
2. **Berita live** (`src/ingestion/news.py` Yahoo RSS per ticker +
   `src/nlp/sentiment.py` FinBERT default / VADER fallback) — LIVE & deskriptif di
   dashboard, **belum di-backtest**. GDELT (`src/ingestion/gdelt.py`, rate-limited)
   baru dipakai untuk studi sampel (`jobs/news_tone_study.py`).
3. **Sentimen kontinu** (`sentiment_engine.py`) — 🚧 **STUB**, belum implementasi.

`event_study.evaluate()` (forecast probabilistik per-event, metodologi
[04_event_study.md](04_event_study.md)) juga masih 🚧 **STUB**.

### Event Drift / PEAD proxy — ✅ SATU-SATUNYA engine tervalidasi

Proxy *post-earnings announcement drift*: deteksi gap harga+volume abnormal
(proxy event laba/berita material) lalu skor arah drift lanjutannya.

- **Vonis US h63:** sector-neutral +0.56%/63d (t 6.4), lolos walk-forward 3 periode
  OOS; versi raw juga lolos. Horizon h21 DITOLAK (sector-neutral gagal).
- **IDX:** kontrarian/negatif → DITOLAK. Edge ini khusus US.
- Karena edge-nya alpha **dalam-sektor**, skor event_drift di produksi
  di-sector-neutralkan cross-sectional per market sebelum masuk composite
  (lihat `jobs/daily_us.py`).

### Insider Engine (`insider_engine.py`) — ❌ DITOLAK, tampil sebagai info

**Input:** tabel `insider_buys` — open-market buy dari SEC Form 4 / bulk Form 345
(`src/ingestion/insider.py`: bulk kuartalan `fetch_quarter` + real-time per emiten
`recent_buys` via Form 4 XML). US-only.

> **Vonis:** abnormal return +0.25%/21d tapi **t hanya 1.25 pada uji non-overlap**
> — tidak signifikan. Bobot composite 0. Sinyal insider tetap ditampilkan di
> dashboard sebagai informasi (independen dari harga/fundamental), dengan deteksi
> staleness data bulk (lag ~1 kuartal).

---

## 5d. Bandarmology Engine (`src/engines/bandarmology_engine.py`) — IDX, proxy GAGAL

**Versi proxy (free) yang terimplementasi:** akumulasi/distribusi via **Chaikin A/D**
dari harga+volume — murni deskriptif.

> **Catatan penting: proxy ini sudah DIUJI dan GAGAL** — di IDX justru
> **kontrarian** (h10 -0.43% t -4.6; h21 -1.02% t -7.3, konsisten di tiga periode
> walk-forward). Bobot composite 0. **Broker summary berbayar dibutuhkan untuk
> versi bandarmology asli** (net per broker, identifikasi broker bandar); tanpa
> itu, klaim "deteksi bandar" tidak jujur.

---

## 5e. Quant / Statistical Engine — 🚧 sebagian besar STUB

- **Regime detection** (`src/features/regime.py`) — 🚧 **STUB**.
- **Forward-return probability** (model klasifikasi → P(naik) + CI) — belum dibangun.
- Yang sudah berjalan dari lapisan ini: metodologi backtest itu sendiri
  (`src/backtest/engine.py`): harga ter-adjust, kuantil cross-sectional per-tanggal,
  walk-forward OOS 3 periode, sector-neutralize opsional.

## Modul lain yang masih STUB (eksplisit, agar tidak menyesatkan)

- `src/engines/sentiment_engine.py` — sentimen kontinu per saham.
- `src/nlp/classify.py` — klasifikasi tipe event berita (LLM).
- `src/features/regime.py` — deteksi regime pasar.
- `src/ingestion/macro.py` — data makro FRED.
- `src/delivery/report.py` — laporan riset naratif (Fase 4).
- `event_study.evaluate()` — forecast probabilistik per-event.

---

## Kontrak output bersama (semua engine) — `src/types.py`

```python
@dataclass
class EngineScore:
    symbol: str
    as_of: date            # PERHATIAN: field-nya `as_of`, bukan `asof`
    engine: str            # "fundamental" | "technical" | "event_drift" | ...
    score: float           # 0..100
    components: dict        # breakdown terukur (audit trail)
    sample_size: int | None # N bila berbasis historis; None bila tidak relevan
    confidence: str         # "normal" | "low"
```

Konsistensi kontrak ini membuat Lapisan 6 (composite) bisa menggabung semua engine
secara seragam, dan membuat halaman Track Record bisa mengaudit tiap komponen.

> **Catatan `CompositeScore`:** field `total` bertipe `float | None` —
> **None bila tidak ada satu pun engine tervalidasi untuk market tersebut**
> (kasus nyata: IDX saat ini). Dashboard menampilkannya apa adanya, bukan
> mengarang angka.
