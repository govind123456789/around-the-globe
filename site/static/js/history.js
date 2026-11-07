/* Country history page: polity map with a time slider, succession-chart clicks, event filters. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const esc = window.atlasEsc;
  const dataEl = $("hist-data");
  const D = dataEl ? JSON.parse(dataEl.textContent) : null;
  const yearLabel = y => (y < 0 ? `${-y} BCE` : `${y} CE`);

  // ---------- event filters ----------
  document.querySelectorAll("[data-ev-filter]").forEach(btn => btn.addEventListener("click", () => {
    const k = btn.dataset.evFilter;
    document.querySelectorAll("[data-ev-filter]").forEach(b => b.classList.toggle("ghost", b !== btn));
    const rows = document.querySelectorAll("#ev-table tbody tr");
    let header = null, any = false;
    const flush = () => { if (header) header.hidden = !any; };
    rows.forEach(r => {
      if (r.classList.contains("century")) { flush(); header = r; any = false; return; }
      const show = k === "all" || r.dataset.kind === k;
      r.hidden = !show; if (show) any = true;
    });
    flush();
  }));

  if (!D || !$("hist-map")) return;

  // ---------- map ----------
  const PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
                   "#9c755f", "#86bcb6", "#d37295", "#8cd17d", "#b6992d", "#499894", "#f1ce63", "#a0cbe8"];
  const colourOf = key => { let h = 0; for (const ch of key) h = (h * 31 + ch.charCodeAt(0)) >>> 0; return PALETTE[h % PALETTE.length]; };
  const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const slider = $("hist-year"), label = $("hist-label"), now = $("hist-now"), tip = document.querySelector(".map-tip");
  const cache = {};
  let map = null, outline = null;

  const loadYear = y => cache[y] || (cache[y] = fetch(`/history/map/${y}.json`).then(r => r.json()).then(gj => {
    gj.features.forEach(f => { f.properties.c = colourOf(f.properties.k); });
    return gj;
  }));

  let ready = false;
  async function show(idx) {
    const y = D.years[idx];
    label.textContent = yearLabel(y);
    if (!ready) return;                    // the map's load handler shows the current slider value
    const gj = await loadYear(y);
    if (D.years[+slider.value] !== y) return;   // a newer slider move superseded this one
    map.getSource("pol").setData(gj);
    // polities whose territory overlaps the country's bounding box (cheap client-side hint)
    const [x0, y0, x1, y1] = D.bbox || [-180, -90, 180, 90];
    const names = new Set();
    for (const f of gj.features) {
      const b = bounds(f.geometry);
      if (b[0] <= x1 && b[2] >= x0 && b[1] <= y1 && b[3] >= y0) names.add(f.properties.n.replace(/^\((.*)\)$/, "$1"));
    }
    now.textContent = names.size ? `Around ${yearLabel(y)}: ${[...names].slice(0, 12).join(", ")}${names.size > 12 ? "…" : ""}` : `No mapped polities near here in ${yearLabel(y)}.`;
  }
  function bounds(g) {
    let a = [180, 90, -180, -90];
    const walk = c => { if (typeof c[0] === "number") { a = [Math.min(a[0], c[0]), Math.min(a[1], c[1]), Math.max(a[2], c[0]), Math.max(a[3], c[1])]; } else c.forEach(walk); };
    walk(g.coordinates); return a;
  }

  function loadLib() {
    if (window.maplibregl) return Promise.resolve(window.maplibregl);
    const base = "https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl";
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = base + ".css"; document.head.appendChild(css);
    return new Promise((res, rej) => { const s = document.createElement("script"); s.src = base + ".js"; s.onload = () => res(window.maplibregl); s.onerror = rej; document.head.appendChild(s); });
  }

  Promise.all([loadLib(), fetch("/geo/countries.json").then(r => r.json())]).then(([lib, geo]) => {
    outline = { type: "FeatureCollection", features: geo.features.filter(f => f.properties.iso3 === D.iso3) };
    const [x0, y0, x1, y1] = D.bbox || [-160, -50, 170, 70];
    const padX = Math.max(4, (x1 - x0) * 0.6), padY = Math.max(3, (y1 - y0) * 0.6);
    map = new lib.Map({
      container: "hist-map", attributionControl: { compact: true, customAttribution: "Cliopatria (Seshat) · Natural Earth" },
      style: { version: 8, sources: {
        world: { type: "geojson", data: geo }, pol: { type: "geojson", data: { type: "FeatureCollection", features: [] } },
        me: { type: "geojson", data: outline } }, layers: [
        { id: "bg", type: "background", paint: { "background-color": cssVar("--surface") } },
        { id: "land", type: "fill", source: "world", paint: { "fill-color": cssVar("--map-na"), "fill-opacity": 0.6 } },
        { id: "pol", type: "fill", source: "pol", paint: { "fill-color": ["get", "c"], "fill-opacity": 0.62 } },
        { id: "pol-line", type: "line", source: "pol", paint: { "line-color": cssVar("--surface"), "line-width": 0.6 } },
        { id: "me", type: "line", source: "me", paint: { "line-color": cssVar("--text"), "line-width": 2.2, "line-dasharray": [2, 1] } },
      ] },
      bounds: [[Math.max(-180, x0 - padX), Math.max(-80, y0 - padY)], [Math.min(180, x1 + padX), Math.min(85, y1 + padY)]],
      renderWorldCopies: false, dragRotate: false, cooperativeGestures: true,
    });
    map.addControl(new lib.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => { ready = true; show(+slider.value); });
    map.on("mousemove", "pol", e => {
      const p = e.features[0].properties;
      tip.style.display = "block"; tip.style.left = Math.min(e.point.x + 14, $("hist-map").clientWidth - 200) + "px"; tip.style.top = (e.point.y + 14) + "px";
      tip.innerHTML = `<b>${esc(p.n.replace(/^\((.*)\)$/, "$1"))}</b><br><span class="muted">${yearLabel(D.years[+slider.value])}</span>`;
    });
    map.on("mouseleave", "pol", () => { tip.style.display = "none"; });
  }).catch(err => { $("hist-map").innerHTML = '<p class="muted" style="padding:16px">The map could not load.</p>'; console.error(err); });

  slider.addEventListener("input", () => show(+slider.value));
  label.textContent = yearLabel(D.years[+slider.value]);

  let timer = null;
  $("hist-play").addEventListener("click", e => {
    if (timer) { clearInterval(timer); timer = null; e.target.textContent = "▶"; return; }
    if (+slider.value >= D.years.length - 1) slider.value = 0;
    e.target.textContent = "❚❚";
    timer = setInterval(() => {
      if (+slider.value >= D.years.length - 1) { clearInterval(timer); timer = null; e.target.textContent = "▶"; return; }
      slider.value = +slider.value + 1; show(+slider.value);
    }, 900);
  });

  // clicking a bar in the succession chart jumps the map to that time
  document.querySelectorAll(".succ rect[data-year]").forEach(r => r.addEventListener("click", () => {
    const y = +r.dataset.year;
    let best = 0;
    D.years.forEach((yy, i) => { if (Math.abs(yy - y) < Math.abs(D.years[best] - y)) best = i; });
    slider.value = best; show(best);
    $("hist-map").scrollIntoView({ behavior: "smooth", block: "center" });
  }));
})();
