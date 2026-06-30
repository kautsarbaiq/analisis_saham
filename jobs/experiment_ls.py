"""Eksperimen: apakah edge bisa jadi TRADEABLE? Long-short & lower-turnover.

Bandingkan 4 varian portofolio dari sinyal composite yang sama:
  long_only / long_short  ×  rebalance mingguan (5h) / bulanan (21h)
Plus uji sensitivitas biaya untuk varian terbaik.

Hipotesis: long_short menghapus drag arah-pasar (tangkap edge RELATIF terbukti);
tapi mean-reversion sinyal 5-hari -> rebalance bulanan bisa membunuh edge-nya.
Semua NET biaya (turnover x cost_bps; long_short kena dua kaki + borrow short).
"""
from __future__ import annotations

from jobs.track_record import build_panels, simulate
from src.storage import db


def _row(label, m):
    hit = (m["hit_rate_vs_bench"] or 0) * 100
    print(f"{label:26}{m['strat_net_total_pct']:>8.1f}{m['strat_gross_total_pct']:>8.1f}"
          f"{m['bench_total_pct']:>8.1f}{(m['sharpe_net'] or 0):>8.2f}{hit:>8.0f}%")


def run() -> None:
    con = db.connect(); db.init_schema(con)
    comp, cl_p = build_panels(con)
    con.close()
    print(f"panel: {comp.shape[1]} simbol x {comp.shape[0]} hari\n")
    print(f"{'VARIAN (NET 15bps)':26}{'NET%':>8}{'GROSS%':>8}{'BENCH%':>8}{'Sharpe':>8}{'hit/pos':>9}")
    print("-" * 67)
    best = None
    for mode in ("long_only", "long_short"):
        for rb in (5, 21):
            m, _ = simulate(comp, cl_p, rebalance=rb, top_n=20, cost_bps=15, mode=mode)
            _row(f"{mode} · {'mingguan' if rb == 5 else 'bulanan'}", m)
            if best is None or m["strat_net_total_pct"] > best[0]:
                best = (m["strat_net_total_pct"], mode, rb)

    print(f"\n>> Terbaik (NET): {best[1]} · {'mingguan' if best[2]==5 else 'bulanan'} "
          f"= {best[0]:+.1f}%")
    print(f"\nSensitivitas biaya utk {best[1]} {best[2]}h:")
    print(f"{'cost_bps':>10}{'NET%':>8}{'Sharpe':>8}")
    for cb in (0, 5, 10, 15, 25):
        m, _ = simulate(comp, cl_p, rebalance=best[2], top_n=20, cost_bps=cb, mode=best[1])
        print(f"{cb:>10}{m['strat_net_total_pct']:>8.1f}{(m['sharpe_net'] or 0):>8.2f}")


if __name__ == "__main__":
    run()
