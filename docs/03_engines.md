# 03 — Spesifikasi Engine Analitis

Setiap engine menghasilkan **skor 0–100** (lebih tinggi = lebih bullish) PLUS
metadata terukur (komponen pembentuk skor, sample size bila relevan). Skor mentah
tidak pernah ditampilkan sebagai "rekomendasi" — ia masuk ke Lapisan 6 dan WAJIB
sudah lewat backtest sebelum dipercaya.

---

## 5a. Fundamental Engine (`src/engines/fundamental_engine.py`)

**Input:** tabel `fundamentals` (dari SEC EDGAR).
**Output:** skor fundamental + breakdown.

Komponen terukur:
- **Valuasi**: P/E, P/B, P/S, EV/EBITDA vs median sektor; DCF sederhana (opsional).
- **Kualitas**: ROE, ROIC, gross/operating margin + tren-nya.
- **Kesehatan**: **Altman Z-Score** (risiko kebangkrutan), current ratio, debt/equity.
- **Kekuatan akrual/akuntansi**: **Piotroski F-Score** (0–9).
- **Pertumbuhan**: CAGR revenue & EPS 3–5 tahun.

> Validasi: ranking fundamental harus memisahkan kinerja masa depan (quantile backtest).
> Jika saham skor-tinggi TIDAK outperform skor-rendah secara terukur → engine ini
> belum boleh diberi bobot besar di composite score.

---

## 5b. Technical Engine (`src/engines/technical_engine.py`)

**Input:** tabel `prices` + `features` (indikator terhitung).
**Output:** skor teknikal + sinyal aktif.

Komponen: tren (MA stack, ADX), momentum (RSI, MACD), volatilitas (ATR, Bollinger),
volume (OBV, volume spike), level (support/resistance, breakout).

> **Aturan keras:** sebuah pola (mis. golden cross) hanya menyumbang skor untuk
> sebuah saham jika pola itu **terbukti punya edge di saham/sektor itu** lewat backtest.
> Tidak ada indikator yang dipercaya hanya karena "kata buku".

---

## 5c. Sentiment / News Engine (`src/engines/sentiment_engine.py` + `event_study.py`)

Dua sub-modul:
1. **Sentimen kontinu** (`sentiment_engine.py`): skor sentimen agregat dari berita
   terbaru per saham (FinBERT/VADER) → komponen skor harian.
2. **Event study** (`event_study.py`): **fitur prediksi unggulan**. Lihat
   [04_event_study.md](04_event_study.md) untuk metodologi lengkap.

> Output event-study SELALU probabilistik + N + CI. Jika N < `MIN_SAMPLE_SIZE` →
> label "LOW CONFIDENCE".

---

## 5d. Bandarmology Engine (`src/engines/bandarmology_engine.py`) — IDX, Fase 3

**Versi proxy (free):**
- Foreign net buy/sell flow (bila tersedia publik).
- Akumulasi/distribusi: OBV, A/D line, Money Flow Index.
- Deteksi *unusual volume* + *price-volume divergence* (volume naik tanpa harga naik =
  indikasi akumulasi diam-diam, ATAU distribusi — dibedakan via konteks).

**Versi premium (saat upgrade):** broker summary asli → net per broker, identifikasi
broker bandar, deteksi akumulasi bertahap.

> Confidence proxy dibatasi & dinyatakan eksplisit; jangan menjual proxy sebagai
> data broker asli.

---

## 5e. Quant / Statistical Engine (`src/features/regime.py` + scoring)

- **Regime detection**: pasar trending / sideways / high-vol? (lookback
  `REGIME_LOOKBACK_DAYS`). Sinyal yang sama bisa berlawanan hasil di regime berbeda.
- **Forward-return probability**: model klasifikasi (logistic / gradient boosting)
  di atas seluruh fitur → P(naik > threshold) per horizon, dengan CI.
- Model ini yang mengubah kumpulan skor menjadi **probabilitas terukur**.

---

## Kontrak output bersama (semua engine)

```python
@dataclass
class EngineScore:
    symbol: str
    asof: date
    engine: str            # "fundamental" | "technical" | ...
    score: float           # 0..100
    components: dict        # breakdown terukur (audit trail)
    sample_size: int | None # N bila berbasis historis; None bila tidak relevan
    confidence: str         # "normal" | "low"
```

Konsistensi kontrak ini membuat Lapisan 6 (composite) bisa menggabung semua engine
secara seragam, dan membuat halaman Track Record bisa mengaudit tiap komponen.
