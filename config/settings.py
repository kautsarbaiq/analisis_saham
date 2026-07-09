"""Konfigurasi global Project Bandar.

Semua angka "magic" (ambang, window, threshold confidence) dikumpulkan di sini agar
strategi bisa di-tune di satu tempat dan mudah di-audit. Tidak ada keputusan terukur
yang boleh hardcoded tersebar di engine.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Path ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DUCKDB_PATH = os.getenv("DUCKDB_PATH", str(DATA_DIR / "bandar.duckdb"))

# --- Kredensial (diambil dari .env) ---
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ----------------------------------------------------------------------------
# PARAMETER STRATEGI (terukur — boleh di-tune, tapi tiap perubahan harus di-backtest)
# ----------------------------------------------------------------------------

# Ambang minimum sample size sebelum sebuah sinyal boleh ditampilkan dengan
# "confidence normal". Di bawah ini → label "LOW CONFIDENCE".
MIN_SAMPLE_SIZE = 30

# Horizon forward-return yang diprediksi & di-backtest (hari perdagangan).
FORWARD_HORIZONS = [1, 5, 21]  # ~1 hari, ~1 minggu, ~1 bulan

# Ambang "pergerakan berarti" untuk klasifikasi naik/turun (per horizon, dalam %).
MOVE_THRESHOLD_PCT = {1: 1.0, 5: 3.0, 21: 5.0}

# Confidence interval yang ditampilkan ke user.
CI_LEVEL = 0.95

# Backtest: rasio split & metode validasi (anti-overfitting).
BACKTEST_TRAIN_RATIO = 0.6
WALK_FORWARD_FOLDS = 5

# Bobot composite score (Lapisan 6). Dijumlahkan jadi 1.0.
# CATATAN: bobot ini HIPOTESIS AWAL; hanya engine yang LULUS backtest (tabel
# `validation`) yang benar-benar diberi bobot di composite. Saat ini hanya
# `mean_reversion` yang tervalidasi -> ia menyetir skor prediktif.
SCORE_WEIGHTS = {
    "shortvol_level": 0.30,   # sinyal terkuat tervalidasi (short seller ter-informasi)
    "event_drift": 0.25,      # PEAD proxy, tervalidasi
    "insider": 0.15,
    "fundamental": 0.12,
    "mean_reversion": 0.08,
    "sentiment": 0.05,
    "technical": 0.03,
    "bandarmology": 0.02,
}

# Regime detection: window untuk menilai kondisi pasar.
REGIME_LOOKBACK_DAYS = 63  # ~1 kuartal

# Rate-limit jeda antar request (detik) agar sopan ke API gratis.
REQUEST_DELAY_SEC = 0.5
