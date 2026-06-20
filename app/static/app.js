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
  initChart();
  if (WL.length) selectSymbol(WL[0].symbol);

  const cmd = document.getElementById("cmd");
  cmd.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const s = e.target.value.trim().toUpperCase();
    if (bySym[s]) { selectSymbol(s); e.target.value = ""; }
    else { e.target.classList.add("err"); setTimeout(() => e.target.classList.remove("err"), 500); }
  });
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

function renderWatchlist() {
  const el = document.getElementById("wl-rows");
  el.innerHTML = WL.map((m) => {
    const up = (m.change_pct || 0) >= 0;
    return `<div class="wl-row" data-sym="${m.symbol}">
      <span class="wl-sym">${m.symbol}</span>
      <span class="num">${fmt.px(m.last)}</span>
      <span class="num ${up ? "up" : "down"}">${fmt.pct(m.change_pct)}</span>
      <span class="wl-spark">${sparkSVG(m.spark, up)}</span>
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

  document.getElementById("detail").innerHTML = `
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
