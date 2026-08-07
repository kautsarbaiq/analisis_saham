# 08 — Cara Pakai (panduan pengguna)

Dokumen ini untuk **Anda yang memakai**, bukan yang membaca kode. Tujuannya satu:
Anda tahu apa yang boleh dan tidak boleh disimpulkan dari angka di layar.

> ⚠️ **Ini alat analisis & edukasi, BUKAN nasihat investasi.** Sistem tidak pernah
> mengeluarkan kata "beli" atau "jual", tidak tahu profil risiko Anda, dan tidak
> menghitung untung-rugi posisi Anda. Keputusan tetap milik Anda.

---

## 1. Apa yang sebenarnya dilakukan sistem ini

Sistem ini **memeringkat saham berdasarkan sinyal yang sudah lolos uji statistik ketat**,
lalu menunjukkan bukti di baliknya. Itu saja — dan itu sudah banyak.

**Yang TIDAK dilakukan (jujur sejak awal):**

| Ekspektasi umum | Kenyataan terukur di sistem ini |
|---|---|
| "Prediksi harga besok" | Tidak bisa. Edge baru terukur di horizon **2–3 bulan**. |
| "Sinyal beli/jual" | Tidak ada. Hanya peringkat + bukti. |
| "Pasti untung" | Tidak. Lihat §6 — sistem lebih sering *salah* di horizon kuartalan. |
| "Semua indikator berguna" | Tidak. Dari ~8 engine, **6 ditolak** karena gagal uji. |

**Yang dilakukan:** dari 548 saham (503 S&P 500 + 45 LQ45), sistem menghitung skor
prediktif hanya dari sinyal yang lolos backtest rigor (harga ter-adjust, kuantil
per-tanggal, walk-forward out-of-sample, sector-neutral). Saat ini **2 sinyal**
untuk US, dan **nol** untuk IDX — jadi skor IDX sengaja kosong.

---

## 2. Persiapan sekali saja

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
```

Lalu isi portofolio Anda di [`config/portfolio.json`](../config/portfolio.json) —
inilah yang membuat berita & digest relevan dengan Anda:

```json
{
  "holdings": [
    {"symbol": "NVDA", "note": "posisi inti"},
    {"symbol": "BBCA.JK"}
  ],
  "watch": ["AMD", "TSM"]
}
```

- `holdings` = yang Anda **miliki**; `watch` = yang Anda **pantau**.
- Simbol US apa adanya (`NVDA`), simbol Indonesia pakai akhiran `.JK` (`BBCA.JK`).
- **Tidak perlu** isi jumlah lot atau harga beli — sistem sengaja tidak menghitung
  untung-rugi Anda (itu ranah nasihat keuangan, bukan alat analisis).
- Kosongkan pun boleh: berita otomatis jatuh ke mode "top screener + makro".

---

## 3. Alur harian

```bash
python -m jobs.refresh          # harga + skor + digest berita (~2-3 menit)
.venv/bin/uvicorn app.server:app --port 8000
```

Buka <http://localhost:8000>. Itu saja untuk pemakaian normal.

**Sesekali** (bukan harian — butuh histori penuh & lambat):

```bash
python -m jobs.effectiveness      # ukur ulang kualitas sinyal (IC, hit-rate)
python -m jobs.track_record       # simulasi portofolio
python -m jobs.backtest_shortvol  # validasi ulang engine short-volume
python -m jobs.news_forward_test  # cek apakah lapisan berita sudah bisa divonis
```

Ingin otomatis tiap pagi? Lihat `scripts/com.projectbandar.daily.plist` (launchd)
atau `.github/workflows/daily_us.yml` (GitHub Actions, gratis).

---

## 4. Membaca dashboard

### Kolom **P** di watchlist — skor prediktif (0–100)
Ini **satu-satunya angka yang punya bukti statistik**. Isinya blend dari engine yang
lolos backtest untuk market itu. Tanda `—` berarti jujur: belum ada edge terukur
(semua saham IDX begini) atau skornya sudah basi >7 hari.

Kolom **F** (fundamental) dan konteks teknikal di panel kanan bersifat **deskriptif** —
ditampilkan untuk konteks, bobotnya nol di skor prediktif karena gagal uji.

### Panel "Skor Prediktif"
- Tag hijau menyebut engine yang **benar-benar menyetir** skor saham itu.
- Blok **"Penyetir skor · tervalidasi"** menampilkan short-volume + % volume jual-pendek.
- Ada tanggal `per YYYY-MM-DD` — kalau tertinggal jauh, skornya memang tidak dipakai.
- Peringatan ⚠ muncul bila salah satu data penyetir telat.

### Tombol **◷ TRACK RECORD**
Simulasi portofolio + blok **"Seberapa efektif sinyalnya?"** (§6). Baca ini sebelum
mempercayai skor apa pun.

### Tombol **✦ BERITA**
Berita yang diperingkat menurut relevansi dengan portofolio Anda. Label:

| Label | Arti |
|---|---|
| `DIMILIKI` | berita tentang saham di `holdings` Anda |
| `DIPANTAU` | saham di `watch` Anda |
| `DISEBUT` | berita pasar yang menyebut nama emiten portofolio Anda |
| `SESEKTOR` | emiten lain di sektor yang Anda miliki |
| `PASAR` | makro/pasar umum |
| `...?` | **judul tidak menyebut emitennya** — keterkaitan lemah, feed RSS memang longgar |

Di tiap berita ada dua kelompok yang **sengaja dipisah**:
- **⚡ vol 4.5x** dan **P 72.9** → **TERUKUR** dari data harga (⚡ = volume abnormal,
  komponen yang sama dengan engine `event_drift` yang tervalidasi). Artinya: *pasar
  sedang bereaksi pada saham ini*.
- **kategori** (laba/M&A/regulasi) dan **sent ±0.xx** → **HEURISTIK**, dari kata kunci
  dan FinBERT. **Belum di-backtest.** Berguna untuk memilih bacaan, **bukan** untuk
  menyimpulkan arah harga.

Angka paling kanan hanyalah **urutan tampilan**, bukan ramalan besar pergerakan.

---

## 5. Cara memakainya dengan benar

1. **Perlakukan sebagai penyaring ide, bukan pemberi perintah.** Skor tinggi = "layak
   diteliti lebih lanjut", bukan "beli".
2. **Horizon 2–3 bulan.** Edge-nya tidak signifikan di bawah ~2 bulan (§6). Memakai
   ini untuk trading mingguan = memakai alat di luar wilayah buktinya.
3. **Jangan terkonsentrasi.** Sistem menang lewat *besaran*, bukan frekuensi — itu
   hanya bekerja bila Anda memegang cukup banyak nama sehingga rata-rata sempat bekerja.
4. **Perhatikan sektor.** Kedua sinyal tervalidasi bersifat *dalam-sektor*
   (sector-neutral), jadi skor tinggi berarti "bagus dibanding sesama sektornya",
   bukan "bagus dibanding semua saham".
5. **Berita = konteks, bukan sinyal.** Pakai ⚡ untuk tahu di mana pasar sedang
   bereaksi; jangan menyimpulkan arah dari sentimen headline.
6. **Kalau `—`, terima saja.** Itu sistem sedang jujur, bukan rusak.

---

## 6. Seberapa efektif, sebenarnya? (angka nyata)

Dijalankan dengan `python -m jobs.effectiveness`, panel composite identik produksi,
501 saham × 1.272 hari:

**Information Coefficient (korelasi rank skor vs return ke depan):**

| Horizon | IC | IR | % hari positif | t (non-overlap) | Vonis |
|---|---|---|---|---|---|
| 5 hari | +0,0063 | +0,10 | 60% | +1,38 | tidak signifikan |
| 10 hari | +0,0097 | +0,15 | 61% | +1,52 | tidak signifikan |
| 21 hari | +0,0170 | +0,28 | 62% | +1,14 | tidak signifikan |
| **42 hari** | **+0,0267** | +0,44 | 65% | **+2,15** | **signifikan ✓** |
| **63 hari** | **+0,0282** | +0,45 | 66% | **+2,36** | **signifikan ✓** |

> IC 0,02–0,05 adalah kisaran **wajar untuk fund kuantitatif sungguhan**. IC di atas
> 0,10 hampir selalu tanda bug atau look-ahead. Angka kita masuk akal — itu justru
> tanda sehat.

**Kuintil** (return rata-rata per kelompok skor) monotonik **hanya** di h42/h63:
di h63, Q0 +3,84% → Q4 +5,46% (spread +1,62%).

**Hit-rate top-20 vs benchmark:**

| Horizon | Menang | Hit-rate (CI 95%) | Saat menang | Saat kalah | Asimetri |
|---|---|---|---|---|---|
| 21 hari | 29/50 | 58,0% (44,2–70,6%) | +2,81% | −1,84% | 1,53× |
| 63 hari | 6/16 | 37,5% (18,5–61,4%) | +5,35% | −2,16% | 2,48× |

**Baca ini pelan-pelan** — ini bagian terpenting dari seluruh dokumen:

- Kedua CI **memuat 50%**, artinya secara statistik kita **belum bisa mengklaim**
  sistem menang lebih *sering* daripada lempar koin.
- Di horizon 63 hari sistem justru **kalah lebih sering** (hanya 6 dari 16 kuartal).
- Tapi rata-rata alpha tetap **positif** (+0,66%/kuartal), karena **saat menang
  menangnya 2,5× lebih besar daripada saat kalah**.

Konsekuensi praktis: **jangan menilai sistem dari satu kuartal**, dan jangan
mempertaruhkan banyak pada satu nama. Ini profil "sering salah kecil, sesekali benar
besar" — profil yang hanya menguntungkan bila dijalankan berulang dan tersebar.

**Per tahun** (top-20 vs benchmark, h21):

| Tahun | Strategi | Benchmark | Alpha | |
|---|---|---|---|---|
| 2022 | −0,28% | −0,25% | −0,03% | ✗ |
| 2023 | +2,14% | +1,46% | +0,68% | ✓ |
| 2024 | +3,26% | +1,93% | +1,33% | ✓ |
| 2025 | +1,68% | +1,22% | +0,46% | ✓ |
| 2026 | +4,37% | +1,68% | +2,69% | ✓ |

4 dari 5 tahun beralpha positif; 2022 (pasar turun) datar.

**Simulasi portofolio** (`jobs/track_record.py`, long-only bulanan top-20, biaya 15 bps):
NET **+125,3%** vs benchmark equal-weight **+75,1%** selama 4,2 tahun (Sharpe 1,04).

---

## 7. Batasan yang harus Anda tahu

1. **Survivorship bias.** Universe = konstituen S&P 500 *saat ini*. Saham yang bangkrut
   atau terdepak tidak ada di data → hasil historis cenderung **optimistis**.
2. **Rezim bull.** Periode uji (2021–2026) didominasi pasar naik.
3. **Short VOLUME ≠ short INTEREST.** Sinyal terkuat memakai volume jual-pendek harian
   FINRA, bukan posisi short outstanding.
4. **IDX belum punya edge terukur.** Bandarmology sungguhan butuh broker summary
   berbayar; proxy gratis sudah diuji dan **gagal**.
5. **Lapisan berita belum tervalidasi.** Arsip sedang dikumpulkan; `jobs.news_forward_test`
   akan memvonis setelah ≥200 pasangan berita-return terkumpul.
6. **Data gratis.** yfinance/RSS legal untuk pemakaian pribadi, **tidak** untuk dijual
   ulang (lihat [02_data_sources.md](02_data_sources.md)).

---

## 8. Kalau ada masalah

| Gejala | Sebab & solusi |
|---|---|
| Kolom P semua `—` | Belum ada engine tervalidasi untuk market itu (normal untuk IDX), atau skor basi → `python -m jobs.refresh` |
| Panel berita kosong | Belum ada digest → `python -m jobs.news_digest` |
| Berita tidak relevan | `config/portfolio.json` masih kosong |
| `IO Error: database is locked` | Server uvicorn masih jalan saat job menulis DB → hentikan server dulu |
| Digest berita lambat | FinBERT sedang memuat model (sekali di awal); berikutnya cepat |
| Ingest FINRA 403 | Normal — hari libur bursa/file belum terbit; job melewatinya dan bisa diulang |

---

**Ringkasan satu kalimat:** sistem ini memberi Anda daftar pendek saham yang layak
diteliti, dengan bukti statistik yang bisa diperiksa dan batasan yang dinyatakan
terbuka — bukan ramalan, dan bukan pengganti keputusan Anda sendiri.
