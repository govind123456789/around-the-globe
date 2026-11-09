/* Decorative rotating globe for hero bands, drawn on a canvas from /geo/countries.json.
   Orthographic projection; rotation pauses off-screen and stays still for reduced motion. */
(() => {
  "use strict";
  const canvas = document.querySelector("[data-globe]");
  if (!canvas || !canvas.getContext) return;
  const ctx = canvas.getContext("2d");
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const RAD = Math.PI / 180;
  const TILT = +(canvas.dataset.tilt || 18) * RAD;
  let lon = +(canvas.dataset.lon || 78);
  let rings = null, size = 0, dpr = 1, visible = true, last = 0;
  const highlight = canvas.dataset.highlight || null;

  function resize() {
    const box = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    size = Math.round(box.width);
    canvas.width = canvas.height = Math.round(size * dpr);
    if (rings) draw();
  }

  function project(lonDeg, latDeg, cosC, sinC) {
    const l = (lonDeg - lon) * RAD, p = latDeg * RAD;
    const cp = Math.cos(p), x = cp * Math.sin(l), y0 = Math.sin(p), z0 = cp * Math.cos(l);
    return [x, y0 * cosC - z0 * sinC, y0 * sinC + z0 * cosC];      // tilt around the x axis
  }

  function trace(path, ring, r, cx, cy, cosC, sinC) {
    const pts = new Array(ring.length);
    let any = false;
    for (let i = 0; i < ring.length; i += 2) {
      let [x, y, z] = project(ring[i], ring[i + 1], cosC, sinC);
      if (z >= 0) any = true;
      else { const n = Math.hypot(x, y) || 1; x /= n; y /= n; }    // pull far-side points to the rim
      pts[i] = cx + x * r; pts[i + 1] = cy - y * r;
    }
    if (!any) return;
    path.moveTo(pts[0], pts[1]);
    for (let i = 2; i < pts.length; i += 2) path.lineTo(pts[i], pts[i + 1]);
    path.closePath();
  }

  const cs = getComputedStyle(canvas);
  const land = cs.getPropertyValue("--globe-land").trim() || "#3d7a62";
  const line = cs.getPropertyValue("--globe-line").trim() || "rgba(255,255,255,.1)";
  const hi = cs.getPropertyValue("--globe-hi").trim() || "#dcc189";
  const sea1 = cs.getPropertyValue("--globe-sea-1").trim() || "#1a4a3c";
  const sea2 = cs.getPropertyValue("--globe-sea-2").trim() || "#0a221b";

  function draw() {
    const w = canvas.width, r = w / 2 - 2 * dpr, c = w / 2;
    const cosC = Math.cos(TILT), sinC = Math.sin(TILT);
    ctx.clearRect(0, 0, w, w);
    ctx.save();
    ctx.beginPath(); ctx.arc(c, c, r, 0, 2 * Math.PI); ctx.clip();
    const sea = ctx.createRadialGradient(c - r * .35, c - r * .4, r * .1, c, c, r);
    sea.addColorStop(0, sea1); sea.addColorStop(1, sea2);
    ctx.fillStyle = sea; ctx.fillRect(0, 0, w, w);

    ctx.strokeStyle = line; ctx.lineWidth = dpr * .6;              // graticule
    for (let la = -60; la <= 60; la += 30) drawLine(i => [i, la], -180, 180, r, c, cosC, sinC);
    for (let lo = -180; lo < 180; lo += 30) drawLine(i => [lo, i], -90, 90, r, c, cosC, sinC);

    const lands = new Path2D(), mine = new Path2D();
    for (const f of rings) trace(f.iso === highlight ? mine : lands, f.ring, r, c, c, cosC, sinC);
    ctx.lineWidth = dpr * .5;
    ctx.strokeStyle = line;
    ctx.fillStyle = land; ctx.fill(lands); ctx.stroke(lands);
    if (highlight) { ctx.fillStyle = hi; ctx.fill(mine); ctx.stroke(mine); }
    const shade = ctx.createRadialGradient(c - r * .3, c - r * .35, r * .3, c, c, r * 1.02);
    shade.addColorStop(0, "rgba(255,255,255,.06)"); shade.addColorStop(.7, "rgba(4,18,13,0)"); shade.addColorStop(1, "rgba(4,18,13,.55)");
    ctx.fillStyle = shade; ctx.fillRect(0, 0, w, w);
    ctx.restore();
    ctx.beginPath(); ctx.arc(c, c, r, 0, 2 * Math.PI);
    ctx.strokeStyle = hi; ctx.globalAlpha = .55; ctx.lineWidth = dpr; ctx.stroke(); ctx.globalAlpha = 1;
  }

  function drawLine(point, a, b, r, c, cosC, sinC) {
    ctx.beginPath();
    let pen = false;
    for (let i = a; i <= b; i += 4) {
      const [lo, la] = point(i);
      const [x, y, z] = project(lo, la, cosC, sinC);
      if (z < 0) { pen = false; continue; }
      const px = c + x * r, py = c - y * r;
      pen ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
      pen = true;
    }
    ctx.stroke();
  }

  let cost = 0, frames = 0, stopped = false;
  function loop(t) {
    if (stopped) return;
    requestAnimationFrame(loop);
    if (!visible || document.hidden || t - last < 100) return;     // 10 redraws a second is smooth at this speed
    lon += Math.min(t - last, 200) * 0.0012;                       // about 1 degree a second
    last = t;
    const start = performance.now();
    draw();
    cost += performance.now() - start;
    if (++frames === 12) {                                         // too slow on this device: stay still
      if (cost / frames > 30) stopped = true;
      cost = 0; frames = 0;
    }
  }

  fetch("/geo/countries.json").then(r => r.json()).then(geo => {
    rings = [];
    for (const f of geo.features) {
      const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
      for (const poly of polys) {
        const src = poly[0];                                       // outer ring only
        let x0 = 180, x1 = -180, y0 = 90, y1 = -90;
        for (const pt of src) { x0 = Math.min(x0, pt[0]); x1 = Math.max(x1, pt[0]); y0 = Math.min(y0, pt[1]); y1 = Math.max(y1, pt[1]); }
        if (f.properties.iso3 !== highlight && (x1 - x0) * (y1 - y0) < 0.6) continue;   // too small to see at this size
        const step = src.length > 120 ? 4 : src.length > 40 ? 3 : src.length > 12 ? 2 : 1, flat = [];
        for (let i = 0; i < src.length; i += step) flat.push(src[i][0], src[i][1]);
        rings.push({ iso: f.properties.iso3, ring: flat });
      }
    }
    resize();
    canvas.classList.add("ready");
    window.addEventListener("resize", resize);
    if (!still) {
      new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(canvas);
      last = performance.now();
      requestAnimationFrame(loop);
    }
  }).catch(() => { canvas.remove(); });
})();
