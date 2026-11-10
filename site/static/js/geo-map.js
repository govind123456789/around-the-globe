/* Conflict event map: UCDP events of the last 12 months on a half-degree grid, as circles sized by
   deaths and coloured by type of violence. Data: /geopolitics/data/events.json
   (each point: [lon, lat, deaths, events, type, conflict, iso3]). */
(() => {
  const el = document.querySelector("[data-event-map]");
  if (!el) return;
  const TYPES = { 1: ["State-based conflict", "#a8432e"], 2: ["Non-state conflict", "#c07a28"], 3: ["One-sided violence", "#5a2a6e"] };
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const lib = () => window.maplibregl ? Promise.resolve(window.maplibregl) : new Promise((res, rej) => {
    const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/static/vendor/maplibre-gl.css"; document.head.appendChild(l);
    const s = document.createElement("script"); s.src = "/static/vendor/maplibre-gl.js"; s.onload = () => res(window.maplibregl); s.onerror = rej; document.head.appendChild(s);
  });
  let started = false;
  async function start() {
    if (started) return; started = true;
    const [L, geo, ev] = await Promise.all([lib(), fetch("/geo/countries.json").then(r => r.json()), fetch("/geopolitics/data/events.json").then(r => r.json())]);
    const pts = { type: "FeatureCollection", features: ev.points.map(p => ({ type: "Feature", geometry: { type: "Point", coordinates: [p[0], p[1]] },
      properties: { d: p[2], n: p[3], t: p[4], c: p[5], iso: p[6] } })) };
    const map = new L.Map({
      container: el, attributionControl: { compact: true, customAttribution: "UCDP · Natural Earth" },
      style: { version: 8, sources: { c: { type: "geojson", data: geo }, e: { type: "geojson", data: pts } }, layers: [
        { id: "bg", type: "background", paint: { "background-color": css("--surface") } },
        { id: "land", type: "fill", source: "c", paint: { "fill-color": css("--surface-2") } },
        { id: "line", type: "line", source: "c", paint: { "line-color": css("--border-strong"), "line-width": 0.5 } },
        { id: "ev", type: "circle", source: "e", paint: {
          "circle-color": ["match", ["get", "t"], 1, TYPES[1][1], 2, TYPES[2][1], TYPES[3][1]],
          "circle-opacity": 0.62, "circle-stroke-color": "#fff", "circle-stroke-width": 0.6,
          "circle-radius": ["interpolate", ["linear"], ["sqrt", ["max", ["get", "d"], 1]], 1, 2.2, 10, 6, 100, 22, 300, 42] } },
      ] },
      bounds: [[-120, -40], [150, 62]], renderWorldCopies: false, dragRotate: false, pitchWithRotate: false, cooperativeGestures: true, maxZoom: 8,
    });
    map.addControl(new L.NavigationControl({ showCompass: false }), "top-right");
    el._map = map;
    map.on("error", e => console.error("event map:", e.error && e.error.message));
    const tip = el.parentElement.querySelector(".map-tip");
    map.on("mousemove", "ev", e => {
      const p = e.features[0].properties;
      if (!tip) return;
      tip.style.display = "block";
      tip.style.left = Math.min(e.point.x + 14, el.clientWidth - 220) + "px"; tip.style.top = (e.point.y + 14) + "px";
      tip.innerHTML = `<b>${esc(p.c)}</b><br>${(+p.d).toLocaleString("en")} deaths in ${p.n} event${p.n == 1 ? "" : "s"}<br><span class="muted">${TYPES[p.t] ? TYPES[p.t][0] : ""}</span>`;
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "ev", () => { if (tip) tip.style.display = "none"; map.getCanvas().style.cursor = ""; });
  }
  const io = "IntersectionObserver" in window && new IntersectionObserver(es => { if (es.some(x => x.isIntersecting)) { io.disconnect(); start(); } });
  if (io) io.observe(el);
  setTimeout(() => { const r = el.getBoundingClientRect(); if (r.top < innerHeight + 300) start(); }, 1200);
  addEventListener("scroll", () => { const r = el.getBoundingClientRect(); if (r.top < innerHeight + 300) start(); }, { passive: true });
})();
