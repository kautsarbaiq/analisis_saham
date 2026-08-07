"""Portofolio user — daftar saham yang DIMILIKI / dipantau khusus.

Dipakai untuk memfilter berita & screener agar relevan dengan posisi nyata user,
bukan seluruh 548 saham. Disimpan di `config/portfolio.json` supaya user bisa
mengeditnya sendiri tanpa menyentuh kode (dan ikut ter-commit bila diinginkan).

Format file (semua field selain `symbol` opsional):
    {
      "holdings": [
        {"symbol": "NVDA", "note": "posisi inti"},
        {"symbol": "BBCA.JK"}
      ],
      "watch": ["AMD", "TSM"]
    }

`holdings` = dimiliki; `watch` = dipantau tapi belum punya. Keduanya dipakai untuk
relevansi berita, dengan holdings diprioritaskan.

CATATAN COMPLIANCE: file ini TIDAK menyimpan jumlah lot/harga beli dan sistem tidak
pernah menghitung untung/rugi atau menyarankan aksi — positioning tetap alat
analisis & edukasi (docs/07_compliance.md).
"""
from __future__ import annotations

import json

from config.settings import ROOT
from config.universe import load_sectors, market_of

PORTFOLIO_FILE = ROOT / "config" / "portfolio.json"


def _norm(sym: str) -> str:
    return sym.strip().upper()


def load() -> dict:
    """Baca portofolio user. Kembalikan {'holdings': [...], 'watch': [...]}.

    Aman: file hilang/rusak -> portofolio kosong (fitur berita jatuh ke mode
    'seluruh universe', bukan error).
    """
    if not PORTFOLIO_FILE.exists():
        return {"holdings": [], "watch": []}
    try:
        raw = json.loads(PORTFOLIO_FILE.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[portfolio] gagal baca {PORTFOLIO_FILE.name}: {exc} — dianggap kosong")
        return {"holdings": [], "watch": []}

    holdings = []
    for h in raw.get("holdings") or []:
        if isinstance(h, str):
            holdings.append({"symbol": _norm(h), "note": ""})
        elif isinstance(h, dict) and h.get("symbol"):
            holdings.append({"symbol": _norm(h["symbol"]), "note": h.get("note", "")})
    watch = [_norm(w) for w in (raw.get("watch") or []) if isinstance(w, str) and w.strip()]
    return {"holdings": holdings, "watch": watch}


def symbols(include_watch: bool = True) -> list[str]:
    """Semua simbol portofolio (holdings dulu, lalu watch; tanpa duplikat)."""
    p = load()
    out = [h["symbol"] for h in p["holdings"]]
    if include_watch:
        out += [w for w in p["watch"] if w not in out]
    return out


def sectors_owned() -> dict[str, list[str]]:
    """Peta sektor -> simbol portofolio di sektor itu (untuk relevansi sektoral)."""
    sec = load_sectors()
    out: dict[str, list[str]] = {}
    for s in symbols():
        out.setdefault(sec.get(s, "?"), []).append(s)
    out.pop("?", None)
    return out


def markets_owned() -> set[str]:
    return {market_of(s) for s in symbols()}


def is_empty() -> bool:
    return not symbols()
