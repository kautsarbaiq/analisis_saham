"""Digest berita harian — berita berdampak yang RELEVAN dgn portofolio user.

Alur:
  1. baca config/portfolio.json (holdings + watch);
  2. tarik RSS per-emiten portofolio + emiten sesektor ber-composite tertinggi
     + feed pasar/makro;
  3. ARSIPKAN semua headline ke tabel `news` (agar lapisan ini bisa di-backtest
     nanti — lihat jobs/news_forward_test.py);
  4. lampirkan konteks TERUKUR dari DB (vol_ratio/event aktif, composite);
  5. urutkan pakai engines/news_impact.rank -> snapshots/news_digest.json
     (dibaca dashboard) + cetak ringkas + Telegram opsional.

Portofolio kosong -> mode "pasar + top screener" supaya tetap berguna.

Jalankan: python -m jobs.news_digest
"""
from __future__ import annotations

import json

from config import portfolio
from config.settings import ROOT
from config.universe import load_sectors
from src.delivery import alerts
from src.engines import news_impact
from src.ingestion import news as news_mod
from src.storage import db

PEERS_PER_SECTOR = 3      # emiten sesektor teratas yang ikut ditarik beritanya
TOP_IF_EMPTY = 5          # bila portofolio kosong: ambil N teratas screener
MAX_ITEMS = 60


def _context(con, symbols: list[str]) -> dict[str, dict]:
    """Konteks TERUKUR per simbol dari DB: vol_ratio & event_drift (batch terbaru)
    + composite prediktif. Dipakai untuk menandai 'pasar sedang bereaksi'."""
    if not symbols:
        return {}
    ph = ",".join("?" * len(symbols))
    ctx: dict[str, dict] = {}
    rows = con.execute(
        f"SELECT symbol, score, components FROM engine_scores "
        f"WHERE engine = 'event_drift' AND symbol IN ({ph}) "
        f"QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1",
        symbols).fetchall()
    for sym, score, comp in rows:
        try:
            c = json.loads(comp) if comp else {}
        except (TypeError, json.JSONDecodeError):
            c = {}
        ctx[sym] = {"event_drift": score, "vol_ratio": c.get("vol_ratio")}
    rows = con.execute(
        f"SELECT symbol, total FROM composite_scores WHERE symbol IN ({ph}) "
        f"AND as_of >= (SELECT max(as_of) FROM composite_scores) - INTERVAL 7 DAY "
        f"QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1",
        symbols).fetchall()
    for sym, total in rows:
        ctx.setdefault(sym, {})["composite"] = round(total, 1) if total is not None else None
    return ctx


def _sector_peers(con, owned_sectors: set[str], exclude: set[str]) -> list[str]:
    """Emiten ber-composite tertinggi di sektor yang user miliki (US saja — RSS
    per-ticker Yahoo tak menyediakan feed untuk .JK)."""
    if not owned_sectors:
        return []
    sec = load_sectors()
    rows = con.execute(
        "SELECT symbol FROM composite_scores WHERE total IS NOT NULL AND market = 'US' "
        "AND as_of >= (SELECT max(as_of) FROM composite_scores) - INTERVAL 7 DAY "
        "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1 "
        "ORDER BY total DESC").fetchall()
    per: dict[str, int] = {}
    out = []
    for (sym,) in rows:
        s = sec.get(sym)
        if s not in owned_sectors or sym in exclude:
            continue
        if per.get(s, 0) >= PEERS_PER_SECTOR:
            continue
        per[s] = per.get(s, 0) + 1
        out.append(sym)
    return out


def run(send: bool = False) -> dict:
    con = db.connect(); db.init_schema(con)
    p = portfolio.load()
    holdings = {h["symbol"] for h in p["holdings"]}
    watch = set(p["watch"])
    owned = holdings | watch

    if not owned:   # portofolio kosong -> pakai top screener supaya tetap berguna
        rows = con.execute(
            "SELECT symbol FROM composite_scores WHERE total IS NOT NULL AND market='US' "
            "AND as_of >= (SELECT max(as_of) FROM composite_scores) - INTERVAL 7 DAY "
            "QUALIFY row_number() OVER (PARTITION BY symbol ORDER BY as_of DESC) = 1 "
            "ORDER BY total DESC LIMIT ?", [TOP_IF_EMPTY]).fetchall()
        watch = {r[0] for r in rows}
        owned = watch
        print(f"[news] portofolio kosong — pakai top screener: {sorted(watch)}")

    sectors = load_sectors()
    owned_sectors = {sectors.get(s) for s in owned} - {None, "?"}
    peers = _sector_peers(con, owned_sectors, exclude=owned)

    items: list[dict] = []
    for sym in sorted(owned):
        if sym.endswith(".JK"):     # feed per-ticker Yahoo tak tersedia utk IDX
            continue
        items += news_mod.fetch_rss(sym, limit=8)
    for sym in peers:
        items += news_mod.fetch_rss(sym, limit=4)
    items += news_mod.fetch_market(limit_per_feed=10)

    # dedup by id (berita sama bisa muncul di beberapa feed)
    uniq: dict[str, dict] = {}
    for it in items:
        if it["title"]:
            uniq.setdefault(it["id"], it)
    items = list(uniq.values())

    saved = news_mod.persist(con, items)
    ctx = _context(con, sorted({i["symbol"] for i in items if i["symbol"]}))
    ranked = news_impact.rank(items, holdings, watch, set(peers), ctx)[:MAX_ITEMS]
    con.close()

    payload = {
        "as_of": max((str(i["available_at"]) for i in items), default=""),
        "portofolio": {"holdings": sorted(holdings), "watch": sorted(watch),
                       "sektor": sorted(owned_sectors), "peers": peers},
        "status_validasi": ("Konteks 'event aktif' & composite = TERUKUR dari harga "
                            "(engine tervalidasi). Kategori berita & sentimen = heuristik "
                            "DESKRIPTIF, belum di-backtest — urutan tampilan, bukan prediksi."),
        "items": [{k: v for k, v in i.items() if k != "available_at"} for i in ranked],
    }
    d = ROOT / "snapshots"; d.mkdir(exist_ok=True)
    (d / "news_digest.json").write_text(json.dumps(payload, indent=2, default=str))

    print(f"[news] {len(items)} headline unik ({saved} tersimpan ke arsip), "
          f"portofolio={sorted(owned) or '-'}, sesektor={peers or '-'}")
    print(f"\n=== TOP BERITA (urutan = relevansi+kategori+event, BUKAN prediksi) ===")
    for i in ranked[:12]:
        tag = f"[{i['relevansi']}]"
        ev = " ⚡EVENT-AKTIF" if i["terukur"]["event_aktif"] else ""
        sym = i.get("symbol") or "PASAR"
        print(f"  {i['impact']:5.1f} {tag:<11} {sym:<8} {i['heuristik']['kategori']:<18}"
              f"{i['title'][:70]}{ev}")

    if send and ranked:
        top = ranked[:8]
        msg = "*BERITA RELEVAN PORTOFOLIO*\n_urutan = relevansi & kategori (heuristik); "\
              "⚡ = volume abnormal terukur_\n\n" + "\n".join(
                  f"`{(i.get('symbol') or 'PASAR'):<7}` {i['title'][:80]}"
                  f"{' ⚡' if i['terukur']['event_aktif'] else ''}" for i in top)
        alerts.send(msg)
    return payload


if __name__ == "__main__":
    import sys
    run(send="--send" in sys.argv)
