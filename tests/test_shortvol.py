"""Test regresi arc short-volume (audit multi-agent 2026-07-16).

Mengunci perbaikan paritas produksi-vs-backtest & pipeline ingest:
- engine memotong data pada as_of (anti look-ahead) + lag-1;
- tanpa data / data kurang / data basi -> None (bukan placeholder 50);
- simbologi FINRA slash (BRK/B) dipetakan ke notasi universe (BRK-B);
- resume ingest: kelengkapan bulan dihitung dari jumlah hari;
- composite renormalisasi atas engine tervalidasi yang HADIR.
"""
from datetime import date

import pandas as pd

from jobs.shortvol_ingest import month_complete
from src.engines import shortvol_engine as sve
from src.ingestion.short_volume import finra_symbol_map
from src.scoring.composite import combine
from src.types import EngineScore


def _sv(last: str = "2026-07-08", days: int = 15, ratio: float = 0.4) -> pd.DataFrame:
    idx = pd.bdate_range(end=last, periods=days)
    return pd.DataFrame({"date": idx, "short_vol": ratio * 100.0, "total_vol": 100.0})


# ---------- engine: paritas anti look-ahead ----------

def test_engine_memotong_data_di_as_of():
    """Skor as_of D hanya boleh memakai data < D (lag-1 publikasi FINRA)."""
    df = _sv(last="2026-07-08")
    # naikkan rasio hanya utk hari-hari terakhir (data "masa depan" utk as_of 06-25)
    df.loc[df["date"] > "2026-06-25", "short_vol"] = 90.0
    s = sve.score("X", df, date(2026, 6, 25))
    assert s is not None
    assert s.components["svr5"] == 0.4  # data Juli TIDAK bocor ke skor 25 Juni


def test_engine_tanpa_data_none():
    assert sve.score("X", None, date(2026, 7, 1)) is None
    assert sve.score("X", pd.DataFrame(), date(2026, 7, 1)) is None


def test_engine_data_basi_none():
    """Data terakhir >7 hari sebelum as_of -> tidak ada skor (bukan skor basi)."""
    assert sve.score("X", _sv(last="2026-07-08"), date(2026, 7, 20)) is None


def test_engine_obs_kurang_none():
    """<3 observasi dalam window -> None (cermin min_periods=3 backtest)."""
    assert sve.score("X", _sv(last="2026-07-08", days=2), date(2026, 7, 9)) is None


def test_engine_skor_normal():
    s = sve.score("X", _sv(ratio=0.4), date(2026, 7, 9))
    assert s is not None and s.score == 60.0 and s.confidence == "normal"
    assert s.components["n_days"] == 5


# ---------- ingest: simbologi & kelengkapan bulan ----------

def test_finra_symbol_map_kelas_saham():
    m = finra_symbol_map({"AAPL", "BRK-B", "BF-B"})
    assert m["BRK/B"] == "BRK-B" and m["BF/B"] == "BF-B" and m["AAPL"] == "AAPL"
    assert "BRK-B" in m  # notasi asli tetap diterima


def test_month_complete_toleransi_libur():
    lo, hi = date(2026, 6, 1), date(2026, 6, 30)  # 22 hari kerja
    assert month_complete(20, lo, hi)
    assert not month_complete(1, lo, hi)  # bulan mati-di-tengah tak boleh di-skip


# ---------- composite: renormalisasi atas engine yang hadir ----------

def _es(engine: str, score: float) -> EngineScore:
    return EngineScore("X", date(2026, 7, 9), engine, score)


def test_composite_renormalisasi_tanpa_shortvol():
    """Simbol tanpa data short-volume dinilai dari engine tervalidasi sisanya."""
    validated = {"event_drift", "shortvol_level"}
    hanya_ed = combine("X", date(2026, 7, 9), [_es("event_drift", 70.0)],
                       validated_engines=validated)
    assert hanya_ed.total == 70.0  # bobot 0.25/0.25 -> renormalisasi penuh

    keduanya = combine("X", date(2026, 7, 9),
                       [_es("event_drift", 70.0), _es("shortvol_level", 30.0)],
                       validated_engines=validated)
    exp = (70.0 * 0.25 + 30.0 * 0.30) / 0.55
    assert abs(keduanya.total - exp) < 0.01
