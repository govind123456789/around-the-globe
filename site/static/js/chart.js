/* Minimal SVG line chart, matching pipeline/svg.py output and CSS classes. */
(() => {
  "use strict";
  function ticks(lo, hi, n = 4) {
    if (hi === lo) hi = lo + 1;
    const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= raw) || raw;
    const out = []; for (let t = Math.floor(lo / step) * step; t <= hi + step * 0.001; t += step) out.push(+t.toFixed(10));
    return out;
  }
  window.atlasLineChart = function (series, { w = 720, h = 260, title = "" } = {}) {
    series = series.filter(s => s.points.length);
    if (!series.length) return '<p class="muted small">No data.</p>';
    const xs = series.flatMap(s => s.points.map(p => p[0])), ys = series.flatMap(s => s.points.map(p => p[1]));
    const x0 = Math.min(...xs), x1 = Math.max(...xs);
    let lo = Math.min(...ys); const hi = Math.max(...ys);
    if (!(lo > 0 && (hi - lo) / hi < 0.8)) lo = Math.min(lo, 0);
    const tk = ticks(lo, hi); lo = tk[0]; const top = tk[tk.length - 1];
    const ml = 56, mr = 16, mt = 12, mb = 28, pw = w - ml - mr, ph = h - mt - mb;
    const X = x => ml + (x - x0) / ((x1 - x0) || 1) * pw, Y = y => mt + ph - (y - lo) / ((top - lo) || 1) * ph;
    const f = window.atlasFmt, esc = window.atlasEsc;
    let s = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(title)}">`;
    for (const t of tk) s += `<line x1="${ml}" x2="${w - mr}" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}" class="grid"/><text x="${ml - 8}" y="${(Y(t) + 4).toFixed(1)}" class="tick" text-anchor="end">${f(t)}</text>`;
    const span = x1 - x0, step = span <= 8 ? 1 : span <= 40 ? 5 : 10;
    for (let y = Math.ceil(x0 / step) * step; y <= x1; y += step) s += `<text x="${X(y).toFixed(1)}" y="${h - 8}" class="tick" text-anchor="middle">${y}</text>`;
    series.forEach((se, i) => {
      const cls = `s${i + 1}`, pts = [...se.points].sort((a, b) => a[0] - b[0]);
      let seg = [pts[0]]; const segs = [];
      for (let k = 1; k < pts.length; k++) { if (pts[k][0] - pts[k - 1][0] > 1) { segs.push(seg); seg = []; } seg.push(pts[k]); }
      segs.push(seg);
      for (const sg of segs) s += sg.length === 1 ? `<circle cx="${X(sg[0][0]).toFixed(1)}" cy="${Y(sg[0][1]).toFixed(1)}" r="2.5" class="pt ${cls}"/>`
        : `<polyline points="${sg.map(p => X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1)).join(" ")}" class="line ${cls}"/>`;
      const l = pts[pts.length - 1];
      s += `<circle cx="${X(l[0]).toFixed(1)}" cy="${Y(l[1]).toFixed(1)}" r="3" class="pt ${cls}"><title>${esc(se.label)} ${l[0]}: ${f(l[1])}</title></circle>`;
    });
    s += "</svg>";
    if (series.length > 1) s += `<div class="legend">${series.map((se, i) => `<span class="key"><i class="sw s${i + 1}"></i>${esc(se.label)}</span>`).join("")}</div>`;
    return s;
  };
})();
