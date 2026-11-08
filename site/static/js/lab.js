/* The Lab: scatter explorer and correlation atlas.
   Statistics match pipeline/lab.py (a test runs both on the same numbers). */
const LabStats = (() => {
  "use strict";
  function ranks(xs) {
    const order = xs.map((v, i) => i).sort((a, b) => xs[a] - xs[b]);
    const out = new Array(xs.length);
    for (let i = 0; i < order.length;) {
      let j = i;
      while (j + 1 < order.length && xs[order[j + 1]] === xs[order[i]]) j++;
      const r = (i + j) / 2 + 1;
      for (let k = i; k <= j; k++) out[order[k]] = r;
      i = j + 1;
    }
    return out;
  }
  function pearson(x, y) {
    const n = x.length;
    if (n < 3) return null;
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += x[i]; my += y[i]; }
    mx /= n; my /= n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) { const a = x[i] - mx, b = y[i] - my; sxy += a * b; sxx += a * a; syy += b * b; }
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : null;
  }
  const spearman = (x, y) => pearson(ranks(x), ranks(y));
  function ols(x, y) {
    const n = x.length;
    const mx = x.reduce((s, v) => s + v, 0) / n, my = y.reduce((s, v) => s + v, 0) / n;
    let sxy = 0, sxx = 0;
    for (let i = 0; i < n; i++) { sxy += (x[i] - mx) * (y[i] - my); sxx += (x[i] - mx) ** 2; }
    const b = sxy / sxx;
    return { a: my - b * mx, b };
  }
  return { ranks, pearson, spearman, ols };
})();
if (typeof module !== "undefined") module.exports = LabStats;

if (typeof document !== "undefined") (() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const S = LabStats;
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  let metaP = null;
  const meta = () => (metaP = metaP || fetch("/lab/meta.json").then(r => r.json()));
  const cache = {};
  const loadInd = id => (cache[id] = cache[id] || fetch(`/v1/latest/indicators/${id}.json`).then(r => r.json()));

  function compact(v, dec = 1) {
    const a = Math.abs(v);
    if (a >= 1e12) return (v / 1e12).toFixed(1) + " tn";
    if (a >= 1e9) return (v / 1e9).toFixed(1) + " bn";
    if (a >= 1e6) return (v / 1e6).toFixed(1) + " m";
    if (a >= 1e4) return Math.round(v / 1e3).toLocaleString("en") + "k";
    if (a >= 100) return Math.round(v).toLocaleString("en");
    return v.toLocaleString("en", { maximumFractionDigits: dec, minimumFractionDigits: 0 });
  }
  function niceTicks(lo, hi, n = 5) {
    if (hi === lo) hi = lo + 1;
    const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map(s => s * mag).find(s => s >= raw);
    const out = [];
    for (let t = Math.ceil(lo / step) * step; t <= hi + step * 1e-6; t += step) out.push(+t.toFixed(10));
    return out;
  }
  function logTicks(lo, hi) {
    const out = [];
    for (let k = Math.floor(lo); k <= Math.ceil(hi); k++) for (const m of (hi - lo < 2.2 ? [1, 2, 5] : [1])) {
      const t = k + Math.log10(m);
      if (t >= lo && t <= hi) out.push(t);
    }
    return out;
  }

  // =================================================================== scatter explorer
  async function scatter() {
    const box = $("lab-plot");
    if (!box) return;
    const M = await meta();
    const ents = Object.fromEntries(M.entities.map(e => [e.id, e]));
    const inds = Object.fromEntries(M.indicators.map(i => [i.id, i]));
    const regions = [...new Set(M.entities.map(e => e.region).filter(Boolean))].sort();
    const palette = ["--series-1", "--series-2", "--series-3", "--series-4", "--series-5", "--series-6", "--series-7"];
    const hidden = new Set();
    const st = { x: "gdp-per-capita-ppp", y: "life-expectancy", lx: 1, ly: 0, yr: "latest", sz: 1, hl: "" };
    for (const [k, v] of new URLSearchParams(location.hash.slice(1))) if (k in st) st[k] = ["lx", "ly", "sz"].includes(k) ? +v : v;
    if (!inds[st.x]) st.x = "gdp-per-capita-ppp";
    if (!inds[st.y]) st.y = "life-expectancy";
    const xs = $("lab-x"), ys = $("lab-y"), yrs = $("lab-year");
    xs.value = st.x; ys.value = st.y; $("lab-lx").checked = !!st.lx; $("lab-ly").checked = !!st.ly; $("lab-size").checked = !!st.sz;
    $("lab-hl").value = st.hl;
    $("lab-names").innerHTML = M.entities.map(e => `<option value="${esc(e.name)}">`).join("");
    const legend = $("lab-legend");
    legend.innerHTML = regions.map((r, i) => `<button type="button" class="lab-reg" data-r="${esc(r)}" aria-pressed="true"><i style="background:var(${palette[i % palette.length]})"></i>${esc(r)}</button>`).join("");
    legend.addEventListener("click", e => {
      const b = e.target.closest(".lab-reg"); if (!b) return;
      const r = b.dataset.r; hidden.has(r) ? hidden.delete(r) : hidden.add(r);
      b.setAttribute("aria-pressed", hidden.has(r) ? "false" : "true"); draw();
    });
    const tip = $("lab-tip");
    let current = [];

    function pick(rows, year) {
      if (!rows) return null;
      if (year === "latest") {
        for (let i = rows.length - 1; i >= 0; i--) {
          const y = rows[i][0];
          if (y <= M.reference_year && y >= M.reference_year - M.max_data_age) return rows[i];
          if (y < M.reference_year - M.max_data_age) return null;
        }
        return null;
      }
      return rows.find(r => r[0] === +year) || null;
    }

    async function draw(resetYears) {
      st.x = xs.value; st.y = ys.value; st.lx = +$("lab-lx").checked; st.ly = +$("lab-ly").checked;
      st.sz = +$("lab-size").checked; st.hl = $("lab-hl").value.trim(); st.yr = yrs.value || "latest";
      const [X, Y] = await Promise.all([loadInd(st.x), loadInd(st.y)]);
      if (resetYears) {
        const years = [];
        for (let y = M.reference_year; y >= 1990; y--) {
          let n = 0;
          for (const e in ents) if (pick(X.data[e], y) && pick(Y.data[e], y)) n++;
          if (n >= 30) years.push(y);
        }
        const keep = years.includes(+st.yr) ? st.yr : "latest";
        yrs.innerHTML = `<option value="latest">Latest (${M.reference_year - M.max_data_age}–${M.reference_year})</option>` + years.map(y => `<option>${y}</option>`).join("");
        yrs.value = keep; st.yr = keep;
      }
      const ix = inds[st.x], iy = inds[st.y];
      let dropped = 0;
      const pts = [];
      for (const e of M.entities) {
        if (hidden.has(e.region)) continue;
        const a = pick(X.data[e.id], st.yr), b = pick(Y.data[e.id], st.yr);
        if (!a || !b) continue;
        if ((st.lx && a[1] <= 0) || (st.ly && b[1] <= 0)) { dropped++; continue; }
        pts.push({ e, x: a[1], y: b[1], xy: a[0], yy: b[0], tx: st.lx ? Math.log10(a[1]) : a[1], ty: st.ly ? Math.log10(b[1]) : b[1] });
      }
      current = pts;
      history.replaceState(null, "", "#" + new URLSearchParams(Object.entries(st).filter(([k, v]) => v !== "")).toString());
      render(pts, ix, iy, dropped);
    }

    function render(pts, ix, iy, dropped) {
      const stats = $("lab-stats");
      if (pts.length < 3) { box.innerHTML = `<p class="muted">Too few countries have both values${st.yr !== "latest" ? " in " + st.yr : ""}. Try “Latest” or another pair.</p>`; stats.innerHTML = ""; $("lab-outliers").innerHTML = ""; return; }
      const X = pts.map(p => p.tx), Y = pts.map(p => p.ty);
      const r = S.pearson(X, Y), rho = S.spearman(X, Y), fit = S.ols(X, Y);
      const resid = pts.map(p => p.ty - (fit.a + fit.b * p.tx));
      const sd = Math.sqrt(resid.reduce((s, v) => s + v * v, 0) / Math.max(1, resid.length - 2)) || 1;
      pts.forEach((p, i) => { p.res = resid[i]; p.z = resid[i] / sd; });

      const W = Math.max(300, box.clientWidth), H = Math.round(Math.min(600, Math.max(320, W * .62)));
      const ml = W < 480 ? 46 : 60, mr = 14, mt = 16, mb = 46;
      let x0 = Math.min(...X), x1 = Math.max(...X), y0 = Math.min(...Y), y1 = Math.max(...Y);
      const px = (x1 - x0) * .04 || 1, py = (y1 - y0) * .06 || 1; x0 -= px; x1 += px; y0 -= py; y1 += py;
      const SX = v => ml + (v - x0) / (x1 - x0) * (W - ml - mr), SY = v => mt + (H - mt - mb) - (v - y0) / (y1 - y0) * (H - mt - mb);
      const xt = st.lx ? logTicks(x0, x1) : niceTicks(x0, x1, W < 480 ? 4 : 6).filter(t => t >= x0 && t <= x1);
      const yt = st.ly ? logTicks(y0, y1) : niceTicks(y0, y1, 5).filter(t => t >= y0 && t <= y1);
      const lab = (t, log) => compact(log ? 10 ** t : t);
      const maxPop = Math.max(...pts.map(p => p.e.pop || 0)) || 1;
      const rad = p => st.sz ? 2.5 + 22 * Math.sqrt((p.e.pop || 0) / maxPop) : 4.5;
      const hl = st.hl.toLowerCase();
      const outl = [...pts].sort((a, b) => b.z - a.z);
      const labelled = new Set([...outl.slice(0, 4), ...outl.slice(-4)].map(p => p.e.id));
      let svg = `<svg class="chart lab-plot" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(iy.name)} against ${esc(ix.name)}">`;
      for (const t of yt) svg += `<line class="grid" x1="${ml}" x2="${W - mr}" y1="${SY(t)}" y2="${SY(t)}"/><text class="tick" x="${ml - 7}" y="${SY(t) + 4}" text-anchor="end">${lab(t, st.ly)}</text>`;
      for (const t of xt) svg += `<line class="grid faint" y1="${mt}" y2="${H - mb}" x1="${SX(t)}" x2="${SX(t)}"/><text class="tick" x="${SX(t)}" y="${H - mb + 18}" text-anchor="middle">${lab(t, st.lx)}</text>`;
      svg += `<text class="tick axis-label" x="${ml + (W - ml - mr) / 2}" y="${H - 6}" text-anchor="middle">${esc(ix.name)}${st.lx ? " (log scale)" : ""}</text>`;
      svg += `<line class="fit" x1="${SX(x0)}" y1="${SY(fit.a + fit.b * x0)}" x2="${SX(x1)}" y2="${SY(fit.a + fit.b * x1)}"/>`;
      for (const p of [...pts].sort((a, b) => rad(b) - rad(a))) {
        const ri = regions.indexOf(p.e.region), col = palette[(ri < 0 ? 0 : ri) % palette.length];
        const on = hl && p.e.name.toLowerCase() === hl;
        svg += `<circle class="pt${on ? " on" : ""}" data-id="${p.e.id}" cx="${SX(p.tx).toFixed(1)}" cy="${SY(p.ty).toFixed(1)}" r="${rad(p).toFixed(1)}" style="fill:var(${col})"/>`;
      }
      // Labels: the highlighted country first, then outliers, skipping any that would overlap
      const boxes = [];
      const order = [...pts].sort((a, b) => (hl && b.e.name.toLowerCase() === hl) - (hl && a.e.name.toLowerCase() === hl) || Math.abs(b.z) - Math.abs(a.z));
      for (const p of order) {
        const on = hl && p.e.name.toLowerCase() === hl;
        if (!on && !labelled.has(p.e.id)) continue;
        const x = SX(p.tx), y = SY(p.ty), right = x > W - 130, wpx = p.e.name.length * 7 + 4;
        const bx = right ? x - 8 - wpx : x + 8, box = [bx, y - 9, bx + wpx, y + 6];
        if (!on && boxes.some(b => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
        boxes.push(box);
        svg += `<text class="pt-label${on ? " on" : ""}" x="${x + (right ? -8 : 8)}" y="${y + 4}" text-anchor="${right ? "end" : "start"}">${esc(p.e.name)}</text>`;
      }
      svg += `<text class="tick axis-label" x="${ml}" y="${mt - 4}">${esc(iy.name)}${st.ly ? " (log scale)" : ""}</text></svg>`;
      box.innerHTML = svg;

      const f2 = v => v === null ? "—" : (v < 0 ? "−" : "") + Math.abs(v).toFixed(2);
      const yearsTxt = st.yr === "latest" ? `each country’s latest value from ${M.reference_year - M.max_data_age} to ${M.reference_year}` : `values for ${st.yr}`;
      stats.innerHTML = `
        <div><b>${pts.length}</b><span>countries</span></div>
        <div><b>${f2(r)}</b><span>Pearson r${st.lx || st.ly ? " (on log values)" : ""}</span></div>
        <div><b>${f2(rho)}</b><span>Spearman ρ (ranks)</span></div>
        <div><b>${r === null ? "—" : Math.round(r * r * 100) + "%"}</b><span>of variation on the line (R²)</span></div>`;
      $("lab-note").textContent = `Using ${yearsTxt}.` + (dropped ? ` ${dropped} countr${dropped === 1 ? "y has" : "ies have"} zero or negative values and can’t be shown on a log scale.` : "") +
        " Dots are coloured by World Bank region" + (st.sz ? " and sized by population." : ".") + " The dashed line is a least-squares fit. Correlation is not causation.";
      const row = p => `<li><a href="/countries/${p.e.slug}/">${esc(p.e.name)}</a><span>${compact(p.y, iy.decimals)} <small class="muted">vs ${compact(st.ly ? 10 ** (fit.a + fit.b * p.tx) : fit.a + fit.b * p.tx, iy.decimals)} expected</small></span></li>`;
      $("lab-outliers").innerHTML = `
        <div><h3>Furthest above the line</h3><ol>${outl.slice(0, 5).map(row).join("")}</ol></div>
        <div><h3>Furthest below the line</h3><ol>${outl.slice(-5).reverse().map(row).join("")}</ol></div>`;
    }

    box.addEventListener("pointermove", e => {
      const c = e.target.closest(".pt");
      if (!c) { tip.hidden = true; return; }
      const p = current.find(q => q.e.id === c.dataset.id); if (!p) return;
      const ix = inds[st.x], iy = inds[st.y];
      tip.innerHTML = `<b>${esc(p.e.name)}</b><br>${esc(ix.name)}: ${compact(p.x, ix.decimals)} <span class="muted">(${p.xy})</span><br>${esc(iy.name)}: ${compact(p.y, iy.decimals)} <span class="muted">(${p.yy})</span>`;
      const r = box.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 230) + "px"; tip.style.top = (e.clientY - r.top + 14) + "px"; tip.hidden = false;
    });
    box.addEventListener("pointerleave", () => { tip.hidden = true; });
    box.addEventListener("click", e => { const c = e.target.closest(".pt"); if (c) location.href = `/countries/${ents[c.dataset.id].slug}/`; });
    for (const id of ["lab-x", "lab-y"]) $(id).addEventListener("change", () => {
      const i = inds[$(id).value]; $(id === "lab-x" ? "lab-lx" : "lab-ly").checked = !!i.log; draw(true);
    });
    for (const id of ["lab-lx", "lab-ly", "lab-size", "lab-year"]) $(id).addEventListener("change", () => draw(false));
    $("lab-hl").addEventListener("change", () => draw(false));
    $("lab-swap").addEventListener("click", () => {
      [xs.value, ys.value] = [ys.value, xs.value];
      const a = $("lab-lx").checked; $("lab-lx").checked = $("lab-ly").checked; $("lab-ly").checked = a; draw(false);
    });
    $("lab-csv").addEventListener("click", () => {
      const ix = inds[st.x], iy = inds[st.y];
      const q = v => `"${String(v).replace(/"/g, '""')}"`;
      const lines = [["entity_id", "name", "region", `${st.x}_year`, st.x, `${st.y}_year`, st.y].join(",")]
        .concat(current.map(p => [p.e.id, q(p.e.name), q(p.e.region || ""), p.xy, p.x, p.yy, p.y].join(",")));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
      a.download = `${st.x}_vs_${st.y}.csv`; a.click(); URL.revokeObjectURL(a.href);
      void ix; void iy;
    });
    $("lab-copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(location.href); $("lab-copy").textContent = "Link copied"; setTimeout(() => { $("lab-copy").textContent = "Copy link"; }, 1800); } catch (e) { prompt("Copy this link:", location.href); }
    });
    let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(() => render(current, inds[st.x], inds[st.y], 0), 150); });
    $("theme-toggle")?.addEventListener("click", () => setTimeout(() => draw(false), 30));
    draw(true);
  }

  // =================================================================== correlation atlas
  async function atlas() {
    const cv = $("corr-canvas");
    if (!cv) return;
    const [C, M] = await Promise.all([fetch("/lab/correlations.json").then(r => r.json()), meta()]);
    const inds = Object.fromEntries(M.indicators.map(i => [i.id, i]));
    const n = C.ids.length, tip = $("corr-tip"), sel = $("corr-ind");
    let cell = 4, focus = -1;
    const hex = h => { h = h.replace("#", ""); if (h.length === 3) h = [...h].map(c => c + c).join(""); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)); };
    function colour(v, neg, pos, mid) {
      const t = Math.min(1, Math.abs(v)), c = v < 0 ? neg : pos;
      return `rgb(${mid.map((m, k) => Math.round(m + (c[k] - m) * t)).join(",")})`;
    }
    function draw() {
      const W = Math.min(cv.parentElement.clientWidth, 760);
      cell = Math.max(3, Math.floor(W / n));
      const size = cell * n, dpr = Math.min(2, devicePixelRatio || 1);
      cv.width = size * dpr; cv.height = size * dpr; cv.style.width = size + "px"; cv.style.height = size + "px";
      const g = cv.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0);
      const neg = hex(css("--series-1") || "#1f5f8b"), pos = hex(css("--series-2") || "#c2571a"), mid = hex(css("--surface") || "#ffffff"), na = css("--surface-2") || "#eee";
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
        const v = C.rho[i][j];
        g.fillStyle = v === null ? na : colour(v, neg, pos, mid);
        g.fillRect(j * cell, i * cell, cell, cell);
      }
      if (focus >= 0) {
        g.strokeStyle = css("--text") || "#000"; g.lineWidth = 1.5;
        g.strokeRect(0.75, focus * cell + .75, size - 1.5, cell - 1.5); g.strokeRect(focus * cell + .75, .75, cell - 1.5, size - 1.5);
      }
    }
    function at(e) {
      const r = cv.getBoundingClientRect();
      const j = Math.floor((e.clientX - r.left) / cell), i = Math.floor((e.clientY - r.top) / cell);
      return i >= 0 && j >= 0 && i < n && j < n ? [i, j] : null;
    }
    const link = (a, b) => `/lab/scatter/#x=${a}&y=${b}&lx=${inds[a]?.log ? 1 : 0}&ly=${inds[b]?.log ? 1 : 0}`;
    cv.addEventListener("pointermove", e => {
      const ij = at(e); if (!ij) { tip.hidden = true; return; }
      const [i, j] = ij, v = C.rho[i][j];
      tip.innerHTML = `<b>${esc(C.names[i])}</b> × <b>${esc(C.names[j])}</b><br>${v === null ? "Too few countries with both" : "ρ = " + (v < 0 ? "−" : "") + Math.abs(v).toFixed(2)} <span class="muted">· ${C.n[i][j]} countries</span>`;
      const r = cv.parentElement.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 260) + "px"; tip.style.top = (e.clientY - r.top + 14) + "px"; tip.hidden = false;
    });
    cv.addEventListener("pointerleave", () => { tip.hidden = true; });
    cv.addEventListener("click", e => { const ij = at(e); if (ij && ij[0] !== ij[1]) location.href = link(C.ids[ij[1]], C.ids[ij[0]]); });

    function list() {
      const i = C.ids.indexOf(sel.value); focus = i; draw();
      const rows = C.ids.map((id, j) => ({ id, j, v: C.rho[i][j] })).filter(r => r.j !== i && r.v !== null)
        .sort((a, b) => Math.abs(b.v) - Math.abs(a.v)).slice(0, 15);
      $("corr-list").innerHTML = rows.map(r => `<li>
          <a href="${link(sel.value, r.id)}" title="${esc(C.names[r.j])}">${esc(C.names[r.j])}</a>
          <span class="corr-bar" aria-hidden="true"><i class="${r.v < 0 ? "c-neg" : "c-pos"}" style="width:${Math.abs(r.v) * 50}%"></i></span>
          <b>${(r.v < 0 ? "−" : "") + Math.abs(r.v).toFixed(2)}</b><small class="muted">${C.n[i][r.j]}</small></li>`).join("");
      history.replaceState(null, "", "#" + sel.value);
    }
    if (location.hash.length > 1 && C.ids.includes(location.hash.slice(1))) sel.value = location.hash.slice(1);
    sel.addEventListener("change", list);
    let t; addEventListener("resize", () => { clearTimeout(t); t = setTimeout(draw, 150); });
    $("theme-toggle")?.addEventListener("click", () => setTimeout(draw, 30));
    matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", draw);
    list();
  }

  scatter();
  atlas();
})();
