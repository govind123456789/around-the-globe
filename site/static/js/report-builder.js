/* Custom country report: everything is computed from /reports/data/<ISO3>.json and meta.json.
   Each indicator row is [year, value, rank, n, year10, value10, regionValue, spark]. */
(() => {
  const form = document.getElementById("rb-form"), out = document.getElementById("rb-out");
  if (!form) return;
  const SUFFIX = { "tonnes": " t", "TWh": " TWh", "GW": " GW", "TEU": " TEU", "million tonne-km": " m t-km", "MtCO₂e": " Mt", "gCO₂e per kWh": " g/kWh" };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let meta = null;

  function compact(v, d) {
    const a = Math.abs(v);
    for (const [div, suf] of [[1e12, " tn"], [1e9, " bn"], [1e6, " m"]]) if (a >= div) return (v / div).toFixed(a < 1e10 ? 2 : 1) + suf;
    return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  function fmt(v, m) {
    if (v == null) return "—";
    let s = compact(v, m.d);
    if (m.u.startsWith("current US$") && !m.u.endsWith("person")) s = "$" + s;
    if (m.u.startsWith("%")) return s + "%";
    return s + (SUFFIX[m.u] || "");
  }
  const relative = m => m.add || m.u.includes("$");
  function change(v0, v1, m) {
    if (v0 == null) return null;
    if (relative(m)) return v0 > 0 ? { t: `${v1 >= v0 ? "+" : ""}${Math.round(100 * (v1 - v0) / v0)}%`, x: (v1 - v0) / v0 } : null;
    const d = v1 - v0;
    return { t: `${d >= 0 ? "+" : ""}${d.toFixed(m.d)}${m.u.startsWith("%") ? " pts" : ""}`, x: d };
  }
  function spark(pts) {
    if (!pts || pts.length < 2) return "";
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const W = 120, H = 34, sx = (x1 - x0) || 1, sy = (y1 - y0) || 1;
    const p = pts.map(([x, y]) => `${(2 + (x - x0) / sx * (W - 4)).toFixed(1)},${(H - 2 - (y - y0) / sy * (H - 4)).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true"><polyline points="${p}" fill="none" stroke="var(--series-1)" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  }
  // percentile position: 0 = best, 1 = worst (ranks are already ordered best-first)
  const pos = r => (r[2] && r[3] > 1) ? (r[2] - 1) / (r[3] - 1) : null;
  const band = p => p == null ? "" : p <= .25 ? "top quarter" : p >= .75 ? "bottom quarter" : p <= .5 ? "upper half" : "lower half";
  const lcName = n => /^[A-Z]{2}/.test(n) ? n : n[0].toLowerCase() + n.slice(1);

  function item(id, r, d) {
    const m = meta.inds[id], [y, v, rk, n, y0, v0, rv, sp] = r;
    const ch = change(v0, v, m), w = m.w;
    let cmp = "";
    if (m.add && w && w[0] === y && w[1] > 0) cmp = `${(100 * v / w[1]) < 0.1 ? "<0.1" : (100 * v / w[1]).toFixed(1)}% of world`;
    else if (!m.add && w) cmp = `World ${fmt(w[1], m)}`;
    const reg = (!m.add && rv != null && d.region) ? `${esc(d.region)} ${fmt(rv, m)}` : "";
    const p = pos(r), tone = m.dir === "neutral" || p == null ? "" : p <= .25 ? " good" : p >= .75 ? " weak" : "";
    const rankTxt = rk ? (m.dir === "neutral" ? `#${rk} of ${n} ${m.add ? "by size" : "highest first"}` : `#${rk} of ${n}`) : "";
    return `<div class="rb-item${tone}">
      <div class="rb-name"><a href="/data/indicators/${id}/">${esc(m.n)}</a></div>
      <div class="rb-val num-up">${fmt(v, m)}</div>
      <div class="rb-meta">${y}${rankTxt ? " · " + rankTxt : ""}${p != null && m.dir !== "neutral" ? ` · <b>${band(p)}</b>` : ""}</div>
      <div class="rb-cmp">${[cmp, reg].filter(Boolean).join(" · ")}</div>
      <div class="rb-foot">${spark(sp)}${ch ? `<span class="rb-ch${m.dir === "neutral" ? "" : ((ch.x > 0) === (m.dir === "higher_better") ? " up" : " down")}">${ch.t} <small>since ${y0}</small></span>` : ""}</div>
    </div>`;
  }

  function topicSummary(d, t, rows) {
    const scored = rows.filter(([id, r]) => meta.inds[id].dir !== "neutral" && pos(r) != null);
    const top = scored.filter(([, r]) => pos(r) <= .25), bottom = scored.filter(([, r]) => pos(r) >= .75);
    const parts = [];
    if (scored.length) parts.push(`${esc(d.name)} is in the top quarter of countries on ${top.length} of ${scored.length} ranked ${esc(t.name.toLowerCase())} indicators and in the bottom quarter on ${bottom.length}.`);
    const size = rows.find(([id]) => meta.inds[id].add);
    if (size) {
      const [id, r] = size, m = meta.inds[id];
      parts.push(`Its ${esc(lcName(m.n))} is ${fmt(r[1], m)} (${r[0]})${r[2] ? `, the ${ordinal(r[2])} largest of ${r[3]} countries` : ""}.`);
    }
    if (top.length) parts.push(`Strongest: ${top.slice(0, 2).map(([id]) => esc(lcName(meta.inds[id].n))).join(" and ")}.`);
    if (bottom.length) parts.push(`Weakest: ${bottom.slice(0, 2).map(([id]) => esc(lcName(meta.inds[id].n))).join(" and ")}.`);
    return parts.join(" ");
  }
  const ordinal = n => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th");

  async function build() {
    const fd = new FormData(form), c = fd.get("c"), topics = fd.getAll("t");
    if (!topics.length) { out.innerHTML = `<p class="muted">Pick at least one topic.</p>`; return; }
    history.replaceState(null, "", `?c=${c}&t=${topics.join(",")}`);
    out.innerHTML = `<p class="muted">Building the report…</p>`;
    meta = meta || await fetch("/reports/data/meta.json").then(r => r.json());
    const d = await fetch(`/reports/data/${c}.json`).then(r => r.json());
    const chosen = meta.topics.filter(t => topics.includes(t.id));
    const all = chosen.flatMap(t => t.inds.filter(i => d.ind[i]).map(i => [i, d.ind[i]]));
    const uniq = [...new Map(all).entries()];
    const ranked = uniq.filter(([id, r]) => meta.inds[id].dir !== "neutral" && pos(r) != null);
    const strengths = ranked.filter(([, r]) => pos(r) <= .25).sort((a, b) => pos(a[1]) - pos(b[1])).slice(0, 5);
    const gaps = ranked.filter(([, r]) => pos(r) >= .75).sort((a, b) => pos(b[1]) - pos(a[1])).slice(0, 5);
    const li = ([id, r]) => `<li><span>${esc(meta.inds[id].n)}</span><span class="mono">#${r[2]} of ${r[3]}</span></li>`;
    const today = new Date().toISOString().slice(0, 10);
    out.innerHTML = `
      <article class="rb-report">
        <header class="rb-cover">
          <span class="eyebrow">Country report · ${today}</span>
          <h2>${esc(d.name)}</h2>
          <p>${d.region ? esc(d.region) + " · " : ""}${chosen.map(t => esc(t.name)).join(", ")}</p>
          <div class="mk-actions no-print"><button class="btn sm" type="button" data-print>Save as PDF</button><button class="btn ghost sm" type="button" data-copy-link>Copy link</button><a class="btn ghost sm" href="/countries/${d.slug}/">Full country profile</a></div>
        </header>
        <div class="grid g2 rb-sw">
          <div class="card rp-section"><h3>Where ${esc(d.name)} leads</h3>${strengths.length ? `<ol class="mk-list">${strengths.map(li).join("")}</ol>` : `<p class="small muted">No indicator in these topics puts it in the top quarter.</p>`}</div>
          <div class="card rp-section"><h3>Where it lags</h3>${gaps.length ? `<ol class="mk-list">${gaps.map(li).join("")}</ol>` : `<p class="small muted">No indicator in these topics puts it in the bottom quarter.</p>`}</div>
        </div>
        ${chosen.map(t => {
          const rows = t.inds.filter(i => d.ind[i]).map(i => [i, d.ind[i]]);
          if (!rows.length) return "";
          return `<section class="rb-topic-sec rp-section"><div class="section-head"><h2>${esc(t.name)}</h2><a class="no-print" href="/markets/${t.id}/">Market page →</a></div>
            <p class="rb-sum">${topicSummary(d, t, rows)}</p>
            <div class="rb-grid">${rows.map(([id, r]) => item(id, r, d)).join("")}</div></section>`;
        }).join("")}
        <p class="small muted">Ranks compare the latest value of each country with data from the last five years, best first (largest first for sizes). Changes compare with the value about ten years earlier. Regional figures are population-weighted averages. Data: release of this site’s open data from the World Bank, Ember, OECD, UNDP and others; see each indicator for its source and licence.</p>
      </article>`;
    out.querySelector("[data-print]").onclick = () => print();
    out.querySelector("[data-copy-link]").onclick = e => { navigator.clipboard?.writeText(location.href); e.target.textContent = "Link copied"; };
    out.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }

  form.addEventListener("submit", e => { e.preventDefault(); build().catch(err => { out.innerHTML = `<p class="muted">Could not load the data (${esc(err.message)}).</p>`; }); });
  form.querySelector("[data-all]").onclick = () => form.querySelectorAll("[name=t]").forEach(x => { x.checked = true; });
  form.querySelector("[data-none]").onclick = () => form.querySelectorAll("[name=t]").forEach(x => { x.checked = false; });
  const q = new URLSearchParams(location.search);
  if (q.get("c")) {
    const sel = document.getElementById("rb-country");
    if ([...sel.options].some(o => o.value === q.get("c"))) sel.value = q.get("c");
    const ts = (q.get("t") || "").split(",");
    if (ts[0]) form.querySelectorAll("[name=t]").forEach(x => { x.checked = ts.includes(x.value); });
    build().catch(() => {});
  }
})();
