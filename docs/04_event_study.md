# 04 — Event Study: Cara Terukur "Menebak dari Berita"

Ini metodologi di balik fitur unggulan: **memprediksi reaksi harga terhadap berita
secara probabilistik**, bukan dukun. Pendekatannya adalah *event study* — metode baku
di riset keuangan akademik & kuantitatif.

## Ide inti

> "Berita X cenderung diikuti pergerakan Y" hanya boleh dikatakan jika kita bisa
> menunjukkan: berapa kali berita serupa terjadi (N), bagaimana sebaran reaksinya,
> dan seberapa pasti (CI). Tanpa itu = opini terlarang.

## Pipeline

```
Berita masuk (GDELT / RSS / NewsAPI)
   │
   1. NORMALISASI: ekstrak (saham terkait, timestamp tersedia, sumber)
   │
   2. KLASIFIKASI tipe event  ──[LLM Groq / aturan]──>
   │      earnings_beat | earnings_miss | guidance_up | guidance_down |
   │      mna | analyst_upgrade | analyst_downgrade | regulatory |
   │      macro | management_change | buyback | dividend | lawsuit | ...
   │      + magnitudo "surprise" (mis. EPS aktual vs estimasi)
   │      + skor sentimen (FinBERT)
   │
   3. MATCHING historis: cari kejadian serupa di masa lalu
   │      kunci match = (tipe_event × sektor × kapitalisasi × regime_pasar)
   │      sumber historis: arsip GDELT + tabel prices internal
   │
   4. UKUR REAKSI tiap kejadian historis:
   │      Abnormal Return (AR) = return saham − return benchmark
   │      Cumulative AR (CAR) untuk horizon [1, 5, 21] hari
   │
   5. AGREGASI jadi distribusi probabilitas:
   │      P(CAR > threshold), median, mean, CI 95%, sebaran, % kasus berlawanan
   │
   6. OUTPUT TERUKUR + GUARDRAIL:
          jika N < MIN_SAMPLE_SIZE  → "LOW CONFIDENCE, N terlalu kecil"
          selain itu                → forecast probabilistik penuh
```

## Contoh output (yang BENAR)

```
Saham: NVDA | Berita: "Earnings beat + guidance dinaikkan"
Tipe event: earnings_beat + guidance_up | surprise: EPS +12% vs estimasi
Historis serupa: N = 146 (tech, large-cap, regime bullish, 2015–2025)

Horizon 1 hari :  median CAR +3.4%  | P(naik>1%) = 71%  | CI [65%, 77%]
Horizon 5 hari :  median CAR +4.1%  | P(naik>3%) = 58%  | CI [50%, 66%]
⚠️ Catatan risiko: 21% kasus historis JUSTRU turun (fenomena "sell-the-news").
Win-rate backtest sinyal ini (out-of-sample): 57%.
```

## Yang membuat ini jujur (bukan overfitting cerita)

1. **Look-ahead bias dijaga**: pakai timestamp *kapan berita tersedia*, bukan kapan
   peristiwa terjadi. Backtest hanya boleh memakai informasi yang ada saat itu.
2. **Benchmark-adjusted**: pakai *abnormal* return (relatif benchmark), agar tidak
   tertukar antara "saham naik" dan "seluruh pasar kebetulan naik".
3. **Regime-aware**: reaksi berita berbeda di pasar bullish vs bearish; matching
   memperhitungkan ini.
4. **Guardrail N**: tidak pernah memberi angka percaya-diri dari sampel kecil.
5. **Disimpan & diaudit**: setiap prediksi masuk tabel `predictions`, lalu dicek
   hasil aktualnya untuk halaman Track Record.

## Batas yang dinyatakan jujur

- Berita yang benar-benar baru/unik (N kecil) → sistem mengaku tidak tahu.
- Pasar bisa sudah "harga-in" berita sebelum rilis (efficient market) → itulah kenapa
  win-rate realistis ~55–60%, bukan 90%.
