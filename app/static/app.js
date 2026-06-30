/* Project Bandar — Terminal frontend logic. */
"use strict";

const fmt = {
  px: (v) => v == null ? "—" : v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  pct: (v) => v == null ? "—" : (v >= 0 ? "+" : "") + v.toFixed(2) + "%",
  vol: (v) => v == null ? "—" : Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(v),
};

let WL = [];            // watchlist metrics
const bySym = {};       // symbol -> metrics
let current = null;
let chart, candle, volSeries, sma20S, sma50S;

document.addEventListener("DOMContentLoaded", boot);

async function boot() {
  startClock();
  await loadWatchlist();
  loadVerdict();
  initChart();
  if (WL.length) selectSymbol(WL[0].symbol);

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
    document.getElementById("tr-verdict").innerHTML =
      `<b>Vonis jujur (rebalance bulanan, NET ${m.cost_bps}bps):</b> NET <b>${sgn(m.strat_net_total_pct)}%</b> ` +
      `(gross ${sgn(m.strat_gross_total_pct)}%) — positif, TAPI jauh di bawah benchmark <b>+${m.bench_total_pct}%</b>. ` +
      `Eksperimen menunjukkan: lower-turnover menyelamatkan dari −21% (mingguan) → +4% (bulanan), tapi ` +
      `<b>long-short JUSTRU GAGAL</b> (gross negatif — men-short pemimpin bull market). ` +
      `Kesimpulan: tak ada varian yang mengalahkan beli-tahan index. Edge nyata tapi <b>tak cukup jadi alpha</b>. ` +
      `Screener = <b>penyaring ide / kesadaran risiko</b>, BUKAN mesin uang. (Survivorship bias → optimistis.)`;
  } catch (e) {
    mEl.innerHTML = '<div class="tr-mc"><div class="v">Gagal memuat</div></div>';
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

async function loadVerdict() {
  const el = document.getElementById("verdict");
  try {
    const v = await (await fetch("/api/validation")).json();
    if (!v.length) { el.innerHTML = '<span class="vtag">info</span> Backtest belum dijalankan.'; return; }
    const names = { mean_reversion: "Mean-reversion", fundamental: "Fundamental", technical: "Teknikal" };
    const byEng = {};
    v.forEach((x) => { (byEng[x.engine] = byEng[x.engine] || []).push(x); });
    const anyOk = v.some((x) => x.validated);
    const order = Object.keys(byEng).sort((a, b) =>
      (byEng[b].some((r) => r.validated) ? 1 : 0) - (byEng[a].some((r) => r.validated) ? 1 : 0));
    const segs = order.map((eng) => {
      const rows = byEng[eng];
      const ok = rows.some((r) => r.validated);
      const sp = rows.map((r) => `${r.horizon_days}h ${r.spread >= 0 ? "+" : ""}${r.spread}%`).join("/");
      const mark = ok ? '<span style="color:#26a69a">✓</span>' : '<span style="color:#ef5350">✗</span>';
      return `<b>${names[eng] || eng}</b> ${mark} (${sp})`;
    });
    el.classList.toggle("ok", anyOk);
    el.innerHTML = `<span class="vtag">${anyOk ? "1 engine tervalidasi" : "belum tervalidasi"}</span>` +
      `<b>Backtest</b> — ${segs.join(" &nbsp;·&nbsp; ")}. ` +
      (anyOk ? "Kolom <b>P</b> (skor prediktif) disetir engine tervalidasi — edge kecil, bukan jaminan."
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
      return `<a class="news-it" href="${esc(it.link)}" target="_blank" rel="noopener">` +
        `<span class="news-sc ${c}">${it.sentiment > 0 ? "+" : ""}${it.sentiment}</span>` +
        `<span class="news-tt">${esc(it.title)}</span></a>`;
    }).join("");
    el.innerHTML = head + items;
  } catch (e) { el.innerHTML = '<div class="hint">Berita tak tersedia.</div>'; }
}

function renderWatchlist() {
  const el = document.getElementById("wl-rows");
  el.innerHTML = WL.map((m) => {
    const up = (m.change_pct || 0) >= 0;
    return `<div class="wl-row" data-sym="${m.symbol}">
      <span class="wl-sym">${m.symbol}</span>
      <span class="num">${fmt.px(m.last)}</span>
      <span class="num ${up ? "up" : "down"}">${fmt.pct(m.change_pct)}</span>
      <span class="wl-fd" title="Fundamental (SEC EDGAR, deskriptif)">${m.fundamental == null ? "—" : Math.round(m.fundamental)}</span>
      <span class="wl-pred" title="Skor prediktif: mean-reversion (TERVALIDASI)">${m.composite == null ? "—" : Math.round(m.composite)}</span>
    </div>`;
  }).join("");
  el.querySelectorAll(".wl-row").forEach((row) =>
    row.addEventListener("click", () => selectSymbol(row.dataset.sym)));
}

function sparkSVG(data, up) {
  if (!data || data.length < 2) return "";
  const w = 56, h = 18, min = Math.min(...data), max = Math.max(...data), rng = (max - min) || 1;
  const pts = data.map((v, i) =>
    `${(i / (data.length - 1) * w).toFixed(1)},${(h - (v - min) / rng * h).toFixed(1)}`).join(" ");
  const col = up ? "#26a69a" : "#ef5350";
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.2"/></svg>`;
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
  document.getElementById("detail").innerHTML = `
    <div>
      <div class="posture-hd"><span class="blk-hd" style="margin:0;color:#26a69a">Skor Prediktif</span><span class="tag" style="background:rgba(38,166,154,.18);color:#26a69a">3 sinyal ✓ tervalidasi</span></div>
      <div style="display:flex;align-items:baseline;gap:8px">
        <span class="posture-score" style="color:#26a69a">${m.composite == null ? "—" : m.composite.toFixed(0)}</span>
        <span style="color:var(--muted);font-size:11px">/100 · mean-reversion + event-drift + insider (edge kecil)</span>
      </div>
      ${subBar("Reversal 1M", mrc.reversal)}
      ${subBar("Oversold RSI", mrc.oversold)}
      ${subBar("Di bawah SMA20", mrc.below_ma)}
      <div class="subrow" style="grid-template-columns:1fr auto;margin-top:7px">
        <span class="sk">Insider 90h (smart money)</span>
        <span class="sv" style="color:${m.insider_buys ? "#26a69a" : "#6a7888"}">${m.insider_buys ? m.insider_buys + "× beli ✓" : "tak ada"}</span>
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
