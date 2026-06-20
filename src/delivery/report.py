"""Laporan riset otomatis ala analis (Lapisan 7, Fase 4).

LLM (Gemini free) HANYA merangkai narasi; SEMUA angka berasal dari engine/DB.
Wajib ada audit anti-halusinasi: setiap angka di laporan dicek cocok dgn sumbernya.
"""
from __future__ import annotations

from datetime import date


def generate(symbol: str, asof: date) -> str:
    """Susun laporan: tesis, valuasi, kualitas, risiko, katalis berita, kesimpulan.

    TODO(impl, Fase 4):
      1. kumpulkan fakta terukur dari engine_scores/features/predictions.
      2. beri LLM HANYA fakta itu + larangan menambah angka di luar konteks.
      3. audit: ekstrak angka di output, verifikasi cocok dgn sumber; tolak bila mengarang.
      4. tempel disclaimer compliance.
    """
    raise NotImplementedError("Implementasi di Fase 4.")
