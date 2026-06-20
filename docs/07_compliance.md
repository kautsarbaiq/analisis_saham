# 07 — Compliance & Positioning Hukum

> ⚠️ Dokumen ini bukan nasihat hukum. Sebelum komersialisasi (Fase 5), konsultasikan
> dengan profesional hukum yang paham regulasi pasar modal ID & US.

## Risiko inti

Begitu Anda **menjual** sesuatu yang menyarankan "beli/jual saham X", Anda bisa masuk
kategori **penasihat investasi berizin**:
- **Indonesia (OJK):** aktivitas "Penasihat Investasi" diatur & wajib izin.
- **AS (SEC):** memberi nasihat investasi berbayar dapat memicu kewajiban registrasi
  sebagai **Investment Adviser (RIA)**.

## Strategi mitigasi: positioning sebagai ALAT, bukan PENASIHAT

| Lakukan ✅ | Hindari ❌ |
|---|---|
| "Alat analisis & edukasi data" | "Rekomendasi beli/jual personal" |
| Sajikan **data & probabilitas terukur** | Beri perintah "BELI sekarang" |
| "Probabilitas historis 62%, N=312" | "Saham ini PASTI naik" |
| Disclaimer jelas di tiap halaman | Menjanjikan profit / win-rate tinggi |
| User menarik kesimpulan sendiri | Mengelola dana / menerima titipan |
| Track record jujur (termasuk yang salah) | Cherry-pick hanya prediksi yang benar |

## Disclaimer wajib (template, untuk versi jual)

> "Platform ini menyediakan analisis data dan probabilitas historis untuk tujuan
> edukasi dan informasi. Ini BUKAN nasihat investasi, ajakan, atau rekomendasi untuk
> membeli/menjual instrumen apa pun. Kinerja masa lalu tidak menjamin hasil masa depan.
> Segala keputusan investasi adalah tanggung jawab pengguna sepenuhnya. Berinvestasi
> mengandung risiko kehilangan modal."

## Konsekuensi arsitektural (sudah dibangun sejak awal)

1. **Bahasa output netral & probabilistik** — engine tidak pernah mengeluarkan kata
   "beli/jual"; ia mengeluarkan skor, probabilitas, N, dan CI.
2. **Pemisahan Data Layer** ([01_architecture.md](01_architecture.md)) — agar data
   gratis (pribadi) tidak ikut terjual.
3. **Track record jujur** — wajib menampilkan prediksi yang salah juga; ini bukan
   sekadar etika, tapi perlindungan dari klaim menyesatkan.
4. **Pemisahan tier privat vs publik** — fitur/data yang tidak berlisensi untuk dijual
   hanya aktif di mode pribadi.
