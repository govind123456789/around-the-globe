/* Timeline map: a choropleth that steps through the years. One set of colour breaks covers all years
   (computed at build time), so colours are comparable over time. Data: /explore/timeline/data/<id>.json */
(() => {
  const el = document.getElementById("tl-map");
  if (!el) return;
  const sel = document.getElementById("tl-ind"), slider = document.getElementById("tl-year"), label = document.getElementById("tl-label"),
        play = document.getElementById("tl-play"), lo = document.getElementById("tl-lo"), hi = document.getElementById("tl-hi");
  const tip = el.parentElement.querySelector(".map-tip");
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = v => Math.abs(v) >= 1e4 ? Math.round(v).toLocaleString("en") : (+v.toFixed(Math.abs(v) < 10 ? 2 : 1)).toString();
  const lib = () => window.maplibregl ? Promise.resolve(window.maplibregl) : new Promise((res, rej) => {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/vendor/maplibre-gl.css"; document.head.appendChild(l);
    const s = document.createElement("script"); s.src = "/static/vendor/maplibre-gl.js"; s.onload = () => res(window.maplibregl); s.onerror = rej; document.head.appendChild(s);
  });
  let map, cur, timer, cache = {};

  const valueAt = (series, y) => { let best = null; for (const [yy, v] of series) { if (yy <= y && yy >= y - 3) best = v; if (yy > y) break; } return best; };
  function expr(d, y) {
    const ramp = [0, 1, 2, 3, 4, 5, 6].map(i => css(`--map-${i}`)), out = ["match", ["get", "iso3"]];
    let n = 0;
    for (const [iso, s] of Object.entries(d.data)) {
      const v = valueAt(s, y);
      if (v == null) continue;
      let b = 0; while (b < 6 && v > d.breaks[b]) b++;
      out.push(iso, ramp[b]); n++;
    }
    out.push(css("--map-na"));
    return n ? out : css("--map-na");
  }
  function draw() {
    if (!map || !cur) return;
    const y = +slider.value;
    label.textContent = y;
    map.setPaintProperty("fill", "fill-color", expr(cur, y));
  }
  async function load(id) {
    cur = cache[id] || (cache[id] = await fetch(`/explore/timeline/data/${id}.json`).then(r => r.json()));
    const years = Object.values(cur.data).flatMap(s => s.map(p => p[0]));
    slider.min = Math.max(1990, Math.min(...years)); slider.max = Math.max(...years);
    if (+slider.value > +slider.max || +slider.value < +slider.min) slider.value = slider.min;
    lo.textContent = fmt(cur.breaks[0]) + (cur.lower_better ? " (better)" : "");
    hi.textContent = fmt(cur.breaks[cur.breaks.length - 1]) + (cur.lower_better ? "" : " ");
    draw();
  }
  async function start() {
    const [L, geo] = await Promise.all([lib(), fetch("/geo/countries.json").then(r => r.json())]);
    map = new L.Map({
      container: el, attributionControl: { compact: true, customAttribution: "Natural Earth" },
      style: { version: 8, sources: { c: { type: "geojson", data: geo } }, layers: [
        { id: "bg", type: "background", paint: { "background-color": css("--surface") } },
        { id: "fill", type: "fill", source: "c", paint: { "fill-color": css("--map-na") } },
        { id: "line", type: "line", source: "c", paint: { "line-color": css("--surface"), "line-width": 0.6 } }] },
      bounds: [[-165, -56], [180, 76]], renderWorldCopies: false, dragRotate: false, cooperativeGestures: true, maxZoom: 6,
    });
    map.addControl(new L.NavigationControl({ showCompass: false }), "top-right");
    map.on("mousemove", "fill", e => {
      const p = e.features[0].properties, s = cur && cur.data[p.iso3], v = s ? valueAt(s, +slider.value) : null;
      tip.style.display = "block"; tip.style.left = Math.min(e.point.x + 14, el.clientWidth - 200) + "px"; tip.style.top = (e.point.y + 14) + "px";
      tip.innerHTML = `<b>${esc(p.name)}</b> · ${slider.value}<br>${v == null ? '<span class="muted">No data</span>' : esc(cur.name) + ": " + fmt(v)}`;
    });
    map.on("mouseleave", "fill", () => { tip.style.display = "none"; });
    map.on("load", () => load(sel.value));
  }
  sel.addEventListener("change", () => load(sel.value));
  slider.addEventListener("input", draw);
  play.addEventListener("click", () => {
    if (timer) { clearInterval(timer); timer = null; play.textContent = "▶ Play"; return; }
    if (+slider.value >= +slider.max) slider.value = slider.min;
    play.textContent = "❚❚ Pause";
    timer = setInterval(() => {
      if (+slider.value >= +slider.max) { clearInterval(timer); timer = null; play.textContent = "▶ Play"; return; }
      slider.value = +slider.value + 1; draw();
    }, matchMedia("(prefers-reduced-motion: reduce)").matches ? 1400 : 650);
  });
  start().catch(err => console.error(err));
})();
