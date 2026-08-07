/* Project Bandar — Terminal frontend logic. */
"use strict";

const fmt = {
  px: (v) => v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v) => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%",
  vol: (v) => v == null ? "—" : Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(v),
};

let WL = [];            // watchlist metrics
const bySym = {};       // symbol -> metrics
let MKT = "ALL";        // filter market aktif: ALL | US | IDX
let VAL = { US: [], IDX: [] };  // engine tervalidasi per market (dari /api/validation)
let chart, candle, volSeries, sma20S, sma50S;

const mktOf = (sym) => (sym.endsWith(".JK") ? "IDX" : "US");

document.addEventListener("DOMContentLoaded", boot);

async function boot() {
  startClock();
  try {
    await loadVerdict();      // isi VAL dulu agar label detail benar
    await loadWatchlist();
  } catch (e) {
    const el = document.getElementById("wl-rows");
    if (el) el.innerHTML = '<div class="hint">Gagal memuat data — apakah server & DB tersedia?</div>';
  }
  initChart();
  if (WL.length) selectSymbol(WL[0].symbol);

  document.querySelectorAll(".mkt-chips button").forEach((b) =>
    b.addEventListener("click", () => {
      MKT = b.dataset.m;
      document.querySelectorAll(".mkt-chips button").forEach((x) => x.classList.toggle("on", x === b));
      renderWatchlist();
    }));

  const cmd = document.getElementById("cmd");
  cmd.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const s = e.target.value.trim().toUpperCase();
    if (bySym[s]) { selectSymbol(s); e.target.value = ""; }
    else { e.target.classList.add("err"); setTimeout(() => e.target.classList.remove("err"), 500); }
  });

  document.getElementById("tr-btn").addEventListener("click", openTrackRecord);
  document.getElementById("tr-close").addEventListener("click", closeTrackRecord);
  document.getElementById("tr-overlay").addEventListener("click", (e) => {
    if (e.target.id === "tr-overlay") closeTrackRecord();
  });

  document.getElementById("news-btn").addEventListener("click", openNews);
  document.getElementById("news-close").addEventListener("click", closeNews);
  document.getElementById("news-overlay").addEventListener("click", (e) => {
    if (e.target.id === "news-overlay") closeNews();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeNews(); closeTrackRecord(); }
  });
}

function closeNews() { document.getElementById("news-overlay").style.display = "none"; }

const REL_STYLE = {
  dimiliki: ["#26a69a", "DIMILIKI"], dipantau: ["#46d3ff", "DIPANTAU"],
  disebut: ["#d2a24a", "DISEBUT"], sesektor: ["#9aa7b4", "SESEKTOR"],
  pasar: ["#6a7888", "PASAR"],
};

async function openNews() {
  const ov = document.getElementById("news-overlay");
  ov.style.display = "flex";
  const body = document.getElementById("news-body");
  const port = document.getElementById("news-port");
  body.innerHTML = '<div class="hint">Memuat…</div>';
  try {
    const d = await (await fetch("/api/news/portfolio")).json();
    if (!d.items || !d.items.length) {
      port.innerHTML = "";
      body.innerHTML = `<div class="hint">Belum ada digest. Jalankan <code>python -m jobs.news_digest</code>` +
        ` (isi dulu <code>config/portfolio.json</code> agar berita disaring ke saham Anda).</div>`;
      return;
    }
    const p = d.portofolio || {};
    const chips = (arr, cls) => (arr || []).map((s) => `<span class="nchip ${cls}">${esc(s)}</span>`).join("");
    const v = d.validasi_berita || {};
    const vtxt = v.cukup
      ? `arsip ${v.n_terpasang} berita — sudah cukup untuk divonis (lihat jobs.news_forward_test)`
      : `arsip ${v.n_arsip || 0} berita, ${v.n_terpasang || 0} terpasang dgn return — <b>belum cukup</b> untuk divonis (butuh ${v.min_n || 200})`;
    port.innerHTML =
      `<div class="nrow"><span class="nlab">Dimiliki</span>${chips(p.holdings, "own") || '<span class="hint">— kosong, isi config/portfolio.json</span>'}</div>` +
      `<div class="nrow"><span class="nlab">Dipantau</span>${chips(p.watch, "watch") || '<span class="hint">—</span>'}</div>` +
      `<div class="nrow"><span class="nlab">Sektor</span>${chips(p.sektor, "sec") || '<span class="hint">—</span>'}</div>` +
      `<div class="nnote">⚡ = <b>volume abnormal terukur</b> (komponen engine event_drift yang TERVALIDASI). ` +
      `Kategori & sentimen = heuristik deskriptif, <b>belum di-backtest</b> — urutan bacaan, bukan prediksi arah. ` +
      `Status uji-maju: ${vtxt}.</div>`;

    body.innerHTML = d.items.map((i) => {
      const relKey = (i.relevansi || "pasar").replace("?", "");
      const [col, lab] = REL_STYLE[relKey] || REL_STYLE.pasar;
      const ragu = (i.relevansi || "").endsWith("?");
      const t = i.terukur || {}, h = i.heuristik || {};
      const sent = h.sentimen == null ? null : h.sentimen;
      const scol = sent > 0.05 ? "#26a69a" : sent < -0.05 ? "#ef5350" : "#9aa7b4";
      return `<div class="nitem">
        <div class="nmeta">
          <span class="nrel" style="color:${col};border-color:${col}">${lab}${ragu ? "?" : ""}</span>
          <span class="nsym">${esc(i.symbol || "PASAR")}</span>
          <span class="ncat">${esc(h.kategori || "umum")}</span>
          ${t.event_aktif ? `<span class="nev" title="Volume ${t.vol_ratio}x rata-rata 20 hari — terukur">⚡ vol ${t.vol_ratio}x</span>` : ""}
          ${t.composite != null ? `<span class="ncomp" title="Skor prediktif tervalidasi">P ${t.composite}</span>` : ""}
          <span class="grow"></span>
          ${sent != null ? `<span style="color:${scol}">sent ${sent > 0 ? "+" : ""}${sent}</span>` : ""}
          <span class="nimp" title="Skor urutan tampilan (bukan prediksi)">${i.impact}</span>
        </div>
        <a class="ntitle" href="${esc(i.url)}" target="_blank" rel="noopener noreferrer">${esc(i.title)}</a>
        <div class="nsrc">${esc(i.source || "")} · ${esc(i.published || "")}${ragu ? " · <i>judul tak menyebut emiten ini — keterkaitan lemah</i>" : ""}</div>
      </div>`;
    }).join("");
  } catch (e) {
    body.innerHTML = '<div class="hint">Gagal memuat digest berita.</div>';
  }
}

function closeTrackRecord() { document.getElementById("tr-overlay").style.display = "none"; }

async function openTrackRecord() {
  const ov = document.getElementById("tr-overlay");
  ov.style.display = "flex";
  const mEl = document.getElementById("tr-metrics");
  try {
    const d = await (await fetch("/api/track_record")).json();
    const m = d.metrics;
    if (!m || !d.curve || !d.curve.length) {
      mEl.innerHTML = '<div class="tr-mc"><div class="v">Belum ada data — jalankan jobs.track_record</div></div>';
      return;
    }
    const mc = (k, v, cls = "") => `<div class="tr-mc"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`;
    const sgn = (x) => (x >= 0 ? "+" : "") + x;
    mEl.innerHTML =
      mc("Strategi NET", sgn(m.strat_net_total_pct) + "%", m.strat_net_total_pct >= 0 ? "up" : "down") +
      mc("Benchmark", sgn(m.bench_total_pct) + "%", "up") +
      mc("Alpha vs bench", sgn(m.alpha_total_pct) + "%", m.alpha_total_pct >= 0 ? "up" : "down") +
      mc("Hit-rate", Math.round(m.hit_rate_vs_bench * 100) + "%") +
      mc("Strategi GROSS", sgn(m.strat_gross_total_pct) + "%", "mut") +
      mc("CAGR net", m.strat_net_cagr_pct + "%", m.strat_net_cagr_pct >= 0 ? "up" : "down") +
      mc("Sharpe net", m.sharpe_net) +
      mc("Max drawdown", m.max_drawdown_pct + "%", "down");
    requestAnimationFrame(() => drawEquity(d.curve));
    const beat = m.strat_net_total_pct > m.bench_total_pct;
    document.getElementById("tr-verdict").innerHTML =
      `<b>Vonis jujur (long-only bulanan, engine tervalidasi saja, NET ${m.cost_bps}bps):</b> ` +
      `NET <b>${sgn(m.strat_net_total_pct)}%</b> (gross ${sgn(m.strat_gross_total_pct)}%) vs benchmark ` +
      `<b>${sgn(m.bench_total_pct)}%</b> — ${beat ? "mengungguli" : "di bawah"} beli-tahan universe. ` +
      `Simulasi memakai composite yang IDENTIK dgn produksi (hanya engine lolos backtest rigor: ` +
      `harga ter-adjust, kuantil per-tanggal, walk-forward OOS). ` +
      `Caveat terukur: survivorship bias (konstituen saat ini) & tanpa slippage di luar biaya — ` +
      `hasil cenderung optimistis. Screener = <b>penyaring ide berbukti</b>, edukasi, bukan jaminan.`;
    loadEffectiveness();
  } catch (e) {
    mEl.innerHTML = '<div class="tr-mc"><div class="v">Gagal memuat</div></div>';
  }
}

async function loadEffectiveness() {
  const el = document.getElementById("eff-body");
  if (!el) return;
  try {
    const d = await (await fetch("/api/effectiveness")).json();
    if (!d.ic || !d.ic.length) {
      el.innerHTML = '<div class="hint">Uji efektivitas belum dijalankan — <code>python -m jobs.effectiveness</code></div>';
      return;
    }
    const icRows = d.ic.map((r) => {
      const ok = r.signifikan;
      return `<tr><td>h${r.horizon_days}</td>
        <td class="num">${r.ic_mean >= 0 ? "+" : ""}${r.ic_mean.toFixed(4)}</td>
        <td class="num">${r.ic_ir >= 0 ? "+" : ""}${r.ic_ir.toFixed(2)}</td>
        <td class="num">${r.pct_positive.toFixed(0)}%</td>
        <td class="num" style="color:${ok ? "#26a69a" : "#9aa7b4"}">${r.t_stat_nonoverlap >= 0 ? "+" : ""}${r.t_stat_nonoverlap.toFixed(2)}</td>
        <td style="color:${ok ? "#26a69a" : "#9aa7b4"}">${ok ? "signifikan ✓" : "tidak signifikan"}</td></tr>`;
    }).join("");
    const yrRows = (d.per_tahun || []).map((y) =>
      `<tr><td>${y.tahun}</td>
       <td class="num">${y.strategi_pct >= 0 ? "+" : ""}${y.strategi_pct}%</td>
       <td class="num">${y.benchmark_pct >= 0 ? "+" : ""}${y.benchmark_pct}%</td>
       <td class="num" style="color:${y.alpha_pct >= 0 ? "#26a69a" : "#ef5350"}">${y.alpha_pct >= 0 ? "+" : ""}${y.alpha_pct}%</td>
       <td>${y.unggul ? "✓" : "✗"}</td></tr>`).join("");
    const h = d.hit_rate_per_horizon || {};
    const hitTxt = Object.entries(h).map(([hz, r]) =>
      `<b>${hz}</b>: ${r.hit_rate_pct}% (${r.menang}/${r.dari}, CI95 ${r.ci95_pct[0]}–${r.ci95_pct[1]}%) — ` +
      `${r.lebih_baik_dari_koin ? "beda dari lempar koin" : "<b>belum</b> beda dari lempar koin"}; ` +
      `menang ${r.alpha_saat_menang_pct}% vs kalah ${r.alpha_saat_kalah_pct}% (asimetri ${r.asimetri}x)`
    ).join("<br>");

    el.innerHTML = `
      <div class="eff-hd">◈ SEBERAPA EFEKTIF SINYALNYA? — uji kualitas sinyal (bukan hasil portofolio)</div>
      <div class="eff-grid">
        <div>
          <div class="eff-sub">Information Coefficient — korelasi rank skor vs return ke depan</div>
          <table class="eff-tbl"><thead><tr><th>Horizon</th><th class="num">IC</th><th class="num">IR</th><th class="num">% hari +</th><th class="num">t</th><th>vonis</th></tr></thead><tbody>${icRows}</tbody></table>
          <div class="eff-note">IC 0,02–0,05 = wajar untuk fund kuantitatif nyata. IC &gt; 0,10 hampir selalu tanda bug/look-ahead.
          Edge di sini <b>baru signifikan pada horizon panjang (h42–h63)</b> — ini alat untuk tesis 2–3 bulan, bukan trading mingguan.</div>
        </div>
        <div>
          <div class="eff-sub">Per tahun — top-20 vs benchmark (h21, non-overlap)</div>
          <table class="eff-tbl"><thead><tr><th>Tahun</th><th class="num">Strategi</th><th class="num">Bench</th><th class="num">Alpha</th><th></th></tr></thead><tbody>${yrRows}</tbody></table>
          <div class="eff-note"><b>Hit-rate:</b><br>${hitTxt}<br><br>
          Artinya: sistem menang lewat <b>besaran</b>, bukan frekuensi. Jangan menilai dari satu periode —
          dan jangan bertaruh besar pada satu nama.</div>
        </div>
      </div>`;
  } catch (e) {
    el.innerHTML = '<div class="hint">Gagal memuat uji efektivitas.</div>';
  }
}

function drawEquity(curve) {
  const cv = document.getElementById("tr-canvas"), dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth || 700, H = cv.clientHeight || 220;
  cv.width = W * dpr; cv.height = H * dpr;
  const x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, W, H);
  const series = [["bench", "#46d3ff"], ["strat_gross", "#6a7888"], ["strat_net", "#26a69a"]];
  let lo = Infinity, hi = -Infinity;
  curve.forEach((p) => series.forEach(([k]) => { lo = Math.min(lo, p[k]); hi = Math.max(hi, p[k]); }));
  const pad = (hi - lo) * 0.08 || 0.1; hi += pad; lo -= pad;
  const pR = 46, pB = 14, pT = 8, pL = 6, cw = W - pR - pL, ch = H - pT - pB;
  const px = (i) => pL + i / (curve.length - 1) * cw, py = (v) => pT + (hi - v) / (hi - lo) * ch;
  x.strokeStyle = "#141c26"; x.fillStyle = "#5a6776"; x.font = "10px ui-monospace,monospace"; x.textBaseline = "middle";
  for (let g = 0; g <= 4; g++) { const v = lo + (hi - lo) * g / 4, yy = py(v); x.beginPath(); x.moveTo(pL, yy); x.lineTo(pL + cw, yy); x.stroke(); x.fillText(((v - 1) * 100).toFixed(0) + "%", pL + cw + 5, yy); }
  if (1 >= lo && 1 <= hi) { const y1 = py(1); x.strokeStyle = "rgba(207,214,224,.25)"; x.setLineDash([3, 3]); x.beginPath(); x.moveTo(pL, y1); x.lineTo(pL + cw, y1); x.stroke(); x.setLineDash([]); }
  series.forEach(([k, col]) => { x.strokeStyle = col; x.lineWidth = 1.4; x.beginPath(); curve.forEach((p, i) => { const xx = px(i), yy = py(p[k]); i ? x.lineTo(xx, yy) : x.moveTo(xx, yy); }); x.stroke(); });
}

/* ---------- Watchlist ---------- */
async function loadWatchlist() {
  const r = await fetch("/api/watchlist");
  WL = await r.json();
  WL.forEach((m) => { bySym[m.symbol] = m; });
  document.getElementById("wl-count").textContent = WL.length;
  document.getElementById("sb-asof").textContent = WL.length ? "ASOF " + WL[0].date : "";
  renderWatchlist();
}

const ENG_NAMES = {
  mean_reversion: "Mean-rev", fundamental: "Fundamental", technical: "Momentum",
  event_drift: "Event-drift", insider: "Insider", low_volatility: "Low-vol",
  shortvol_level: "Short-vol", shortvol_chg: "Short-vol Δ", bandarmology: "Bandar-proxy",
};

async function loadVerdict() {
  const el = document.getElementById("verdict");
  try {
    const v = await (await fetch("/api/validation")).json();
    if (!v.length) { el.innerHTML = '<span class="vtag">info</span> Backtest belum dijalankan.'; return; }

    VAL = { US: [], IDX: [] };
    v.filter((x) => x.validated).forEach((x) => {
      const m = x.market || "US";
      if (!VAL[m].includes(x.engine)) VAL[m].push(x.engine);
    });

    const seg = (mkt) => {
      const rows = v.filter((x) => (x.market || "US") === mkt);
      if (!rows.length) return `<b>${mkt}</b>: belum diuji`;
      const byEng = {};
      rows.forEach((x) => { (byEng[x.engine] = byEng[x.engine] || []).push(x); });
      const parts = Object.keys(byEng)
        .sort((a, b) => (byEng[b].some((r) => r.validated) ? 1 : 0) - (byEng[a].some((r) => r.validated) ? 1 : 0))
        .map((eng) => {
          const ok = byEng[eng].some((r) => r.validated);
          const mark = ok ? '<span style="color:#26a69a">✓</span>' : '<span style="color:#ef5350">✗</span>';
          return `${ENG_NAMES[eng] || eng}${mark}`;
        });
      return `<b>${mkt}</b>: ${parts.join(" ")}`;
    };

    const anyOk = VAL.US.length + VAL.IDX.length > 0;
    el.classList.toggle("ok", anyOk);
    const tag = `${VAL.US.length + VAL.IDX.length} engine tervalidasi`;
    el.innerHTML = `<span class="vtag">${anyOk ? tag : "belum tervalidasi"}</span>` +
      `<b>Backtest rigor</b> (adj-price · kuantil per-tanggal · OOS) — ${seg("US")} &nbsp;·&nbsp; ${seg("IDX")}. ` +
      (anyOk ? "Kolom <b>P</b> hanya disetir engine ✓ market ybs — edge kecil, bukan jaminan."
             : "Semua skor deskriptif, bukan sinyal beli.");
  } catch (e) { el.innerHTML = '<span class="vtag">info</span> Vonis backtest tak tersedia.'; }
}

function subBar(label, val) {
  const v = val == null ? 0 : Math.max(0, Math.min(100, val));
  return `<div class="subrow"><span class="sk">${label}</span>` +
    `<div class="bar"><div class="fill" style="left:0;width:${v}%;background:#d2a24a"></div></div>` +
    `<span class="sv">${val == null ? "—" : val.toFixed(0)}</span></div>`;
}

function esc(s) {
  return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function loadNews(sym) {
  const el = document.getElementById("news-block");
  if (!el) return;
  el.innerHTML = '<div class="hint">Memuat berita…</div>';
  try {
    const d = await (await fetch("/api/news/" + encodeURIComponent(sym))).json();
    const s = d.summary;
    if (!s || !s.count) { el.innerHTML = '<div class="hint">Tidak ada berita.</div>'; return; }
    const col = s.avg > 0.05 ? "#26a69a" : s.avg < -0.05 ? "#ef5350" : "#9aa7b4";
    const head = `<div class="news-sum">Sentimen rata-rata <b style="color:${col}">${s.avg > 0 ? "+" : ""}${s.avg}</b>` +
      ` · <span class="up">${s.pos}▲</span> <span class="down">${s.neg}▼</span> <span class="mut">${s.neu}●</span> / ${s.count} berita</div>`;
    const items = d.items.slice(0, 8).map((it) => {
      const c = it.sentiment > 0.05 ? "up" : it.sentiment < -0.05 ? "down" : "mut";
      const safeHref = /^https?:\/\//i.test(it.link || "") ? esc(it.link) : "#";  // blokir javascript: dll
      return `<a class="news-it" href="${safeHref}" target="_blank" rel="noopener">` +
        `<span class="news-sc ${c}">${it.sentiment > 0 ? "+" : ""}${it.sentiment}</span>` +
        `<span class="news-tt">${esc(it.title)}</span></a>`;
    }).join("");
    el.innerHTML = head + items;
  } catch (e) { el.innerHTML = '<div class="hint">Berita tak tersedia.</div>'; }
}

function fmtCompact(v) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(v || 0);
}

async function loadInsider(sym) {
  const el = document.getElementById("insider-block");
  if (!el) return;
  const head = (txt, col) => `<div class="subrow" style="grid-template-columns:1fr auto"><span class="sk">Insider buys (real-time 180h · info, belum tervalidasi)</span><span class="sv" style="color:${col}">${txt}</span></div>`;
  try {
    const d = await (await fetch("/api/insider/" + encodeURIComponent(sym))).json();
    if (!d.count) { el.innerHTML = head("tak ada", "#6a7888"); return; }
    const items = d.buys.slice(0, 4).map((b) =>
      `<div class="news-it" style="grid-template-columns:54px 1fr"><span class="news-sc up">$${fmtCompact(b.value)}</span>` +
      `<span class="ntt">${esc(b.date)} · ${esc(b.role)}</span></div>`).join("");
    el.innerHTML = head(`$${fmtCompact(d.total_value)} · ${d.n_insiders} insider ✓`, "#26a69a") + items;
  } catch (e) { el.innerHTML = head("—", "#6a7888"); }
}

function renderWatchlist() {
  const el = document.getElementById("wl-rows");
  const view = WL.filter((m) => MKT === "ALL" || mktOf(m.symbol) === MKT);
  // Skor prediktif dulu (null tenggelam), lalu fundamental sbg tie-break deskriptif.
  view.sort((a, b) => ((b.composite ?? -1) - (a.composite ?? -1)) || ((b.fundamental ?? -1) - (a.fundamental ?? -1)));
  document.getElementById("wl-count").textContent = view.length;
  el.innerHTML = view.map((m) => {
    const up = (m.change_pct || 0) >= 0;
    const noP = m.composite == null;
    const pTitle = noP
      ? "Belum ada engine tervalidasi utk market ini — skor prediktif tidak tersedia (jujur)"
      : "Skor prediktif: hanya engine yang LOLOS backtest rigor utk market ini";
    return `<div class="wl-row" data-sym="${m.symbol}">
      <span class="wl-sym">${m.symbol}</span>
      <span class="num">${fmt.px(m.last)}</span>
      <span class="num ${up ? "up" : "down"}">${fmt.pct(m.change_pct)}</span>
      <span class="wl-fd" title="Fundamental (SEC EDGAR, deskriptif)">${m.fundamental == null ? "—" : Math.round(m.fundamental)}</span>
      <span class="wl-pred${noP ? " na" : ""}" title="${pTitle}">${noP ? "—" : Math.round(m.composite)}</span>
    </div>`;
  }).join("");
  el.querySelectorAll(".wl-row").forEach((row) =>
    row.addEventListener("click", () => selectSymbol(row.dataset.sym)));
}

/* ---------- Chart ---------- */
function initChart() {
  const el = document.getElementById("chart");
  chart = LightweightCharts.createChart(el, {
    layout: { background: { color: "transparent" }, textColor: "#6a7888", fontFamily: "'JetBrains Mono', monospace", fontSize: 10 },
    grid: { vertLines: { color: "#141c26" }, horzLines: { color: "#141c26" } },
    rightPriceScale: { borderColor: "#1b2531", scaleMargins: { top: 0.08, bottom: 0.28 } },
    timeScale: { borderColor: "#1b2531", rightOffset: 4 },
    crosshair: { mode: 0, vertLine: { color: "#3f4b59", labelBackgroundColor: "#1b2531" }, horzLine: { color: "#3f4b59", labelBackgroundColor: "#1b2531" } },
  });

  candle = chart.addCandlestickSeries({
    upColor: "#26a69a", downColor: "#ef5350", borderVisible: false,
    wickUpColor: "#26a69a", wickDownColor: "#ef5350",
  });
  sma20S = chart.addLineSeries({ color: "#ffb000", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  sma50S = chart.addLineSeries({ color: "#46d3ff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  volSeries = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
  volSeries.priceScale().applyOptions({ scaleMargins: { top: 0.78, bottom: 0 } });

  chart.subscribeCrosshairMove((p) => {
    if (!p || !p.seriesData) return;
    const bar = p.seriesData.get(candle);
    if (bar) setOHLC(bar);
  });

  new ResizeObserver(() => {
    chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
  }).observe(el);
  chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
}

function setOHLC(bar) {
  const up = bar.close >= bar.open;
  const c = up ? "up" : "down";
  document.getElementById("c-ohlc").innerHTML =
    `O<b>${fmt.px(bar.open)}</b> H<b>${fmt.px(bar.high)}</b> L<b>${fmt.px(bar.low)}</b> ` +
    `C<b class="${c}">${fmt.px(bar.close)}</b>`;
}

/* ---------- Selection ---------- */
async function selectSymbol(sym) {
  current = sym;
  document.querySelectorAll(".wl-row").forEach((r) => r.classList.toggle("sel", r.dataset.sym === sym));
  document.getElementById("c-sym").textContent = sym;
  renderDetail(bySym[sym]);
  loadNews(sym);
  loadInsider(sym);

  const r = await fetch("/api/ohlc/" + encodeURIComponent(sym));
  if (!r.ok) return;
  const d = await r.json();
  candle.setData(d.bars);
  volSeries.setData(d.volume);
  sma20S.setData(d.sma20);
  sma50S.setData(d.sma50);
  chart.timeScale().fitContent();
  if (d.bars.length) setOHLC(d.bars[d.bars.length - 1]);
}

/* ---------- Detail / analytics panel ---------- */
function pctIn(v, lo, hi) {
  if (v == null || lo == null || hi == null || hi <= lo) return 0;
  return Math.max(0, Math.min(100, (v - lo) / (hi - lo) * 100));
}

function rsiTag(v) {
  if (v == null) return ["nt", "N/A"];
  if (v >= 70) return ["ob", "Overbought"];
  if (v <= 30) return ["os", "Oversold"];
  return ["nt", "Netral"];
}

function renderDetail(m) {
  if (!m) { document.getElementById("detail").innerHTML = '<div class="hint">Tidak ada data.</div>'; return; }
  const up = (m.change_pct || 0) >= 0;
  const rangePos = pctIn(m.last, m.lo52, m.hi52);
  const [rcls, rlabel] = rsiTag(m.rsi14);
  const rsiPos = m.rsi14 == null ? 0 : Math.max(0, Math.min(100, m.rsi14));
  const rsiColor = m.rsi14 >= 70 ? "var(--down)" : m.rsi14 <= 30 ? "var(--up)" : "var(--amber)";

  const stat = (k, v, cls = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${cls}">${v}</div></div>`;

  const pc = m.posture_comp || {};
  const fc = m.fundamental_comp || {};
  const fs = fc.sub_scores || {};
  const pctv = (x) => x == null ? "—" : (x * 100).toFixed(0) + "%";
  const mrc = m.mr_comp || {};
  const mkt = mktOf(m.symbol);
  // Hanya engine yg BENAR-BENAR menyetir composite saham ini: tervalidasi ∩ ada di
  // breakdown produksi. Audit fix: tanpa fallback "breakdown kosong -> semua" —
  // fallback lama bisa mengklaim engine yang tak pernah diproduksi (shortvol_chg).
  const bdKeys = Object.keys(m.composite_breakdown || {});
  const engs = (VAL[mkt] || [])
    .filter((e) => bdKeys.includes(e))
    .map((e) => ENG_NAMES[e] || e);
  const hasP = m.composite != null && engs.length > 0;
  const lowConf = hasP && m.composite_conf === "low";
  const predTag = hasP
    ? `<span class="tag" style="background:rgba(38,166,154,.18);color:#26a69a">${engs.join(" + ")} ✓ tervalidasi (${mkt})</span>`
    : `<span class="tag unval">${m.composite_stale ? "skor lama (basi) disembunyikan — jujur" : `belum ada engine tervalidasi (${mkt})`}</span>`;
  const asOf = m.composite_as_of ? ` · per ${m.composite_as_of}` : "";
  document.getElementById("detail").innerHTML = `
    <div>
      <div class="posture-hd"><span class="blk-hd" style="margin:0;color:#26a69a">Skor Prediktif</span>${predTag}</div>
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="posture-score" style="color:${hasP ? "#26a69a" : "var(--muted)"}">${hasP ? m.composite.toFixed(0) : "—"}</span>
        <span style="color:var(--muted);font-size:11px">${hasP ? `/100 · hanya engine lolos backtest rigor (edge kecil, bukan jaminan)${asOf}` : "tidak tersedia — belum ada edge terukur utk market ini (jujur)"}</span>
      </div>
      ${lowConf ? `<div style="color:#f0b90b;font-size:10px;margin-top:3px">⚠ confidence rendah — ada sinyal penyetir yang datanya telat/stale</div>` : ""}
      ${hasP && m.shortvol != null ? `<div class="blk-hd" style="margin-top:9px;color:#26a69a">Penyetir skor · tervalidasi (sector-neutral)</div>
      <div class="subrow"><span class="sk">Short-volume${m.shortvol_svr5 != null ? ` · ${(m.shortvol_svr5 * 100).toFixed(0)}% vol jual-pendek 5h` : ""}${m.shortvol_conf === "low" ? " · ⚠ telat" : ""}</span><div class="bar"><div class="fill" style="left:0;width:${Math.max(0, Math.min(100, m.shortvol))}%;background:#26a69a"></div></div><span class="sv">${Math.round(m.shortvol)}</span></div>` : ""}
      <div class="blk-hd" style="margin-top:9px;color:var(--faint)">Konteks teknikal · deskriptif (tidak menyetir skor)</div>
      ${subBar("Reversal 1M", mrc.reversal)}
      ${subBar("Oversold RSI", mrc.oversold)}
      ${subBar("Di bawah SMA20", mrc.below_ma)}
      <div id="insider-block" style="margin-top:7px">
        <div class="subrow" style="grid-template-columns:1fr auto"><span class="sk">Insider buys (real-time)</span><span class="sv mut">memuat…</span></div>
      </div>
    </div>

    <div>
      <div class="posture-hd"><span class="blk-hd" style="margin:0;color:#46d3ff">Fundamental · SEC</span>${m.fundamental_conf === "low" ? '<span class="tag unval">low-conf</span>' : '<span class="tag unval">belum tervalidasi</span>'}</div>
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="posture-score" style="color:#46d3ff">${m.fundamental == null ? "—" : m.fundamental.toFixed(0)}</span>
        <span style="color:var(--muted);font-size:11px">/100 · deskriptif</span>
      </div>
      ${subBar("Quality", fs.quality)}
      ${subBar("Profitability", fs.profitability)}
      ${subBar("Growth", fs.growth)}
      ${subBar("Health", fs.health)}
      <div class="stat-grid" style="margin-top:8px">
        ${stat("Piotroski", fc.piotroski == null ? "—" : fc.piotroski + "/9")}
        ${stat("Altman Z", fc.altman_z == null ? "—" : fc.altman_z)}
        ${stat("ROE", pctv(fc.roe))}
        ${stat("Net margin", pctv(fc.net_margin))}
        ${stat("Rev growth", pctv(fc.rev_growth), (fc.rev_growth || 0) >= 0 ? "up" : "down")}
        ${stat("EPS growth", pctv(fc.eps_growth), (fc.eps_growth || 0) >= 0 ? "up" : "down")}
      </div>
    </div>

    <div>
      <div class="posture-hd"><span class="blk-hd" style="margin:0">Tech Posture</span><span class="tag unval">belum tervalidasi</span></div>
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="posture-score">${m.posture == null ? "—" : m.posture.toFixed(0)}</span>
        <span style="color:var(--muted);font-size:11px">/100 · deskriptif, bukan sinyal beli</span>
      </div>
      ${subBar("Tren", pc.trend)}
      ${subBar("Momentum 3M", pc.momentum_3m)}
      ${subBar("Postur RSI", pc.rsi_posture)}
    </div>

    <div>
      <div class="blk-hd">Harga · ${m.date}</div>
      <div class="stat-grid" style="margin-top:8px">
        ${stat("Last", fmt.px(m.last))}
        ${stat("Change %", fmt.pct(m.change_pct), up ? "up" : "down")}
        ${stat("Open", fmt.px(m.open))}
        ${stat("Prev Close", fmt.px(m.prev_close))}
        ${stat("High", fmt.px(m.high))}
        ${stat("Low", fmt.px(m.low))}
        ${stat("Volume", fmt.vol(m.volume))}
        ${stat("Change", fmt.px(m.change), up ? "up" : "down")}
      </div>
    </div>

    <div>
      <div class="blk-hd">Rentang 52 Minggu</div>
      <div class="bar" style="margin-top:8px">
        <div class="fill" style="left:0;width:100%;background:var(--grid)"></div>
        <div class="mk" style="left:${rangePos}%"></div>
      </div>
      <div class="bar-row"><span>${fmt.px(m.lo52)}</span><span>${rangePos.toFixed(0)}%</span><span>${fmt.px(m.hi52)}</span></div>
    </div>

    <div>
      <div class="blk-hd">Momentum · RSI(14)</div>
      <div style="display:flex;align-items:center;gap:8px;margin-top:8px">
        <span class="rsi-val" style="color:${rsiColor}">${m.rsi14 == null ? "—" : m.rsi14.toFixed(1)}</span>
        <span class="tag ${rcls}">${rlabel}</span>
      </div>
      <div class="bar" style="margin-top:6px">
        <div class="fill" style="left:0;width:${rsiPos}%;background:${rsiColor}"></div>
      </div>
      <div class="bar-row"><span>0</span><span>30</span><span>70</span><span>100</span></div>
    </div>

    <div>
      <div class="blk-hd">Tren · Moving Average</div>
      <div class="stat-grid" style="margin-top:8px">
        ${stat("SMA 20", fmt.px(m.sma20), m.last >= m.sma20 ? "up" : "down")}
        ${stat("SMA 50", fmt.px(m.sma50), m.last >= m.sma50 ? "up" : "down")}
        ${stat("SMA 200", fmt.px(m.sma200), m.last >= m.sma200 ? "up" : "down")}
        ${stat("vs SMA200", m.sma200 ? fmt.pct((m.last / m.sma200 - 1) * 100) : "—", m.last >= m.sma200 ? "up" : "down")}
      </div>
    </div>

    <div>
      <div class="posture-hd"><span class="blk-hd" style="margin:0;color:#d2a24a">Berita &amp; Sentimen</span><span class="tag unval">live · belum di-backtest</span></div>
      <div id="news-block"><div class="hint">Memuat berita…</div></div>
    </div>
  `;
}

/* ---------- Clock ---------- */
function startClock() {
  const el = document.getElementById("clock");
  const tick = () => {
    const d = new Date();
    el.textContent = d.toLocaleTimeString("en-GB", { hour12: false }) + " " +
      Intl.DateTimeFormat().resolvedOptions().timeZone.split("/").pop();
  };
  tick();
  setInterval(tick, 1000);
}
