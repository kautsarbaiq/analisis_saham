# 05 — Backtesting & Anti-Overfitting

Backtesting adalah **lapisan kejujuran** sistem. Tanpa ini, semua skor hanyalah opini
berpakaian angka. Dengan ini, setiap klaim punya bukti terukur — atau ditolak.

## Apa yang di-backtest

1. Tiap **sinyal/pola** (golden cross, RSI oversold, dst) → punya edge atau tidak?
2. Tiap **engine** (quantile test: portofolio skor-tinggi vs skor-rendah).
3. **Composite score** & bobotnya.
4. Tiap **tipe event** di event-study.

## Metrik wajib (ditampilkan apa adanya)

| Metrik | Arti |
|---|---|
| Win-rate | % prediksi yang benar arah |
| Avg return / trade | rata-rata return per sinyal |
| Sharpe ratio | return disesuaikan risiko |
| Max drawdown | kerugian beruntun terburuk |
| Profit factor | total profit / total loss |
| Sample size (N) | jumlah kejadian — penentu kepercayaan |
| Precision/Recall | untuk classifier event berita |

## Bahaya yang HARUS dicegah (kalau tidak, backtest bohong)

1. **Look-ahead bias** — memakai data yang belum tersedia saat itu.
   *Mitigasi:* setiap baris data punya kolom "tersedia sejak"; backtest difilter ke
   informasi yang ada pada `asof`.
2. **Survivorship bias** — hanya menguji saham yang masih hidup hari ini.
   *Mitigasi:* sertakan saham delisting; minimal, tandai keterbatasan ini di output.
3. **Overfitting** — model hafal masa lalu, gagal di masa depan.
   *Mitigasi:* **walk-forward validation** (`WALK_FORWARD_FOLDS`), uji *out-of-sample*,
   dan utamakan model sederhana yang dapat dijelaskan.
4. **Data snooping / p-hacking** — mencoba 1000 strategi lalu pamer yang kebetulan bagus.
   *Mitigasi:* catat SEMUA strategi yang diuji; sesuaikan ekspektasi untuk multiple testing.
5. **Biaya transaksi & slippage** — backtest tanpa biaya selalu terlihat indah.
   *Mitigasi:* kurangi return dengan asumsi biaya & spread realistis.

## Walk-forward (default)

```
|----- train -----|-- test --|
        |----- train -----|-- test --|
                |----- train -----|-- test --|
   (geser maju; uji hanya pada periode yang belum pernah dilihat model)
```

## Aturan tayang (gerbang ke produksi)

Sebuah sinyal/engine boleh diberi bobot di composite score HANYA jika:
- `N >= MIN_SAMPLE_SIZE`, DAN
- edge-nya bertahan **out-of-sample** (bukan cuma di train), DAN
- tetap positif **setelah biaya transaksi**.

Jika gagal salah satu → sinyal tetap dihitung & ditampilkan, tapi diberi label
"belum tervalidasi" dan **bobot 0** di skor akhir.

## Track Record (akuntabilitas berjalan)

Setiap prediksi live disimpan, lalu dievaluasi saat horizon-nya lewat
(`jobs/track_record.py`). Halaman Track Record menampilkan akurasi aktual sistem
secara publik — inilah yang membuat produk layak dipercaya & dijual.
