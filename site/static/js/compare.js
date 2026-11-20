/* Compare 2–5 countries in the browser, from the same JSON files as the rest of the site.
   State lives in the address: /compare/?c=ind,chn,usa&v=table|trends|profile&i=<indicator>, so every view
   can be shared. (Old links with #c=IND,CHN still work.) Each country keeps one colour from the chart palette. */
(() => {
  "use strict";
  const ids = JSON.parse(document.getElementById("cmp-countries").textContent);
  const names = JSON.parse(document.getElementById("cmp-names").textContent);
  const nameToId = Object.fromEntries(names.map((n, i) => [n.toLowerCase(), ids[i]]));
  const idToName = Object.fromEntries(ids.map((id, i) => [id, names[i]]));
  const add = document.getElementById("cmp-add"), chips = document.getElementById("cmp-chips"), out = document.getElementById("cmp-out");
  const esc = window.atlasEsc;
  const cache = {};
  let meta = null;
  const THEMES = [["economy", "Economy"], ["human", "Human development"], ["innovation", "Innovation"], ["health", "Health"],
    ["education", "Education"], ["environment", "Environment"], ["society", "Society & inclusion"], ["governance", "Governance"]];

  function state() {
    const p = new URLSearchParams(location.search), h = location.hash.match(/c=([A-Za-z,]+)/);
    const raw = (p.get("c") || (h && h[1]) || "").toUpperCase().split(",");
    return { c: [...new Set(raw.filter(x => idToName[x]))].slice(0, 5), v: p.get("v") || "table", i: p.get("i") || "gdp-per-capita-ppp" };
  }
  function setState(next, push = true) {
    const s = { ...state(), ...next }, p = new URLSearchParams();
    if (s.c.length) p.set("c", s.c.map(x => x.toLowerCase()).join(","));
    if (s.v !== "table") p.set("v", s.v);
    if (s.v === "trends") p.set("i", s.i);
    const url = location.pathname + (p.toString() ? "?" + p.toString().replace(/%2C/g, ",") : "");
    history[push ? "pushState" : "replaceState"](null, "", url);
    render();
  }

  add.addEventListener("change", () => {
    const id = nameToId[add.value.trim().toLowerCase()];
    const s = state();
    if (id && !s.c.includes(id) && s.c.length < 5) { setState({ c: [...s.c, id] }); add.value = ""; }
    else if (s.c.length >= 5) add.setCustomValidity("Up to five countries");
  });
  chips.addEventListener("click", e => { const b = e.target.closest("[data-rm]"); if (b) setState({ c: state().c.filter(x => x !== b.dataset.rm) }); });
  document.getElementById("cmp-copy")?.addEventListener("click", e => {
    navigator.clipboard?.writeText(location.href).then(() => { e.target.textContent = "Link copied"; setTimeout(() => (e.target.textContent = "Copy link"), 1600); });
  });
  document.querySelector(".cmp-views")?.addEventListener("click", e => { const b = e.target.closest("[data-view]"); if (b) setState({ v: b.dataset.view }); });

  const load = id => cache[id] || (cache[id] = fetch(`/v1/latest/entities/country/${id}.json`).then(r => r.json()));
  const loadMeta = () => meta || (meta = Promise.all([fetch("/v1/latest/indicators.json").then(r => r.json()), fetch("/v1/latest/rankings.json").then(r => r.json())]));
  const SHORT = { "wb-wdi": "WB", "wb-wgi": "WB WGI", "undp-hdr": "UNDP", "un-wpp": "UN", "ilostat": "ILO", "faostat": "FAO", "ember": "Ember",
    "oecd": "OECD", "v-dem": "V-Dem", "ti-cpi": "TI", "gdelt": "GDELT", "factbook": "CIA" };

  function leader(ind, vals) {
    if (!["higher_better", "lower_better"].includes(ind.direction)) return -1;
    let best = -1;
    vals.forEach((v, k) => { if (v && (best < 0 || (ind.direction === "higher_better" ? v.value > vals[best].value : v.value < vals[best].value))) best = k; });
    return vals.filter(Boolean).length > 1 ? best : -1;
  }
  function tableView(inds, ents) {
    const dims = [...new Set(inds.map(i => i.dimension))];
    let html = `<div class="table-wrap"><table id="cmp-table"><thead><tr><th>Indicator</th>${ents.map((e, k) => `<th class="num"><i class="sw s${k + 1}"></i> ${esc(e.name)}</th>`).join("")}</tr></thead>`;
    for (const d of dims) {
      const rows = inds.filter(i => i.dimension === d && ents.some(e => e.latest[i.indicator_id]));
      if (!rows.length) continue;
      html += `<tbody><tr class="dim-row"><th colspan="${ents.length + 1}" scope="rowgroup">${esc((THEMES.find(t => t[0] === d) || [d, d])[1])}</th></tr>`;
      for (const ind of rows) {
        const vals = ents.map(e => e.latest[ind.indicator_id]);
        const lead = leader(ind, vals), years = new Set(vals.filter(Boolean).map(v => v.year));
        html += `<tr><td><a href="/data/indicators/${ind.indicator_id}/">${esc(ind.name)}</a>${years.size > 1 ? ' <span class="small stale">⚠ years differ</span>' : ""}</td>` +
          vals.map((v, k) => `<td class="num${k === lead ? " lead" : ""}">${v ? `<span class="n">${NF.value(v.value, ind.decimals ?? 2, ind.unit)}</span>${k === lead ? '<span class="sr-only"> (ahead)</span>' : ""}<span class="sb sb-static" title="${esc(v.source)} · ${esc(v.source_licence)}">${SHORT[v.source] || esc(v.source)} · ${v.year}</span>` : '<span class="muted">—</span>'}</td>`).join("") + "</tr>";
      }
      html += "</tbody>";
    }
    return html + '</table></div><p class="small muted">Bold marks the country ahead, by each indicator’s own direction; neutral indicators have no leader. Badges give the source and data year. <button class="btn ghost sm" id="cmp-csv" type="button">Download CSV</button></p>';
  }
  function trendsView(inds, ents, sel) {
    const usable = inds.filter(i => ents.some(e => (e.series[i.indicator_id] || []).length > 1));
    const ind = usable.find(i => i.indicator_id === sel) || usable[0];
    const series = ents.map((e, k) => ({ label: e.name, points: e.series[ind.indicator_id] || [], cls: `s${k + 1}` }));
    const missing = ents.filter(e => !(e.series[ind.indicator_id] || []).length).map(e => e.name);
    return `<label class="field cmp-ind">Indicator <select id="cmp-ind">${usable.map(i => `<option value="${i.indicator_id}"${i === ind ? " selected" : ""}>${esc(i.name)}</option>`).join("")}</select></label>
      <div class="card"><h3>${esc(ind.name)} <span class="muted small">${esc(ind.unit)}</span></h3>${window.atlasLineChart(series, { title: ind.name })}
      ${missing.length ? `<p class="small muted">No data for ${missing.map(esc).join(", ")}.</p>` : ""}</div>`;
  }
  function profileView(inds, ents) {
    // each axis: the average of the country's percentile ranks (0-100, higher is better) on the theme's indicators
    // that have a direction; neutral indicators are left out; an axis needs 3 or more such indicators with data
    const dirInds = inds.filter(i => i.direction !== "neutral");
    const scores = ents.map(e => THEMES.map(([d]) => {
      const ps = dirInds.filter(i => i.dimension === d).map(i => e.percentiles[i.indicator_id]).filter(p => p !== undefined && p !== null);
      return ps.length >= 3 ? ps.reduce((a, b) => a + b, 0) / ps.length : null;
    }));
    const W = 420, C = W / 2, R = 150, n = THEMES.length;
    const pt = (k, v) => [C + Math.sin(2 * Math.PI * k / n) * R * v / 100, C - Math.cos(2 * Math.PI * k / n) * R * v / 100];
    let svg = `<svg class="radar" viewBox="0 0 ${W} ${W}" role="img" aria-label="Profile of ${ents.map(e => esc(e.name)).join(", ")} across ${n} themes">`;
    for (const r of [25, 50, 75, 100]) svg += `<polygon class="rg" points="${THEMES.map((_, k) => pt(k, r).join(",")).join(" ")}"/>`;
    THEMES.forEach(([, label], k) => { const [x, y] = pt(k, 118); svg += `<line class="rg" x1="${C}" y1="${C}" x2="${pt(k, 100)[0]}" y2="${pt(k, 100)[1]}"/><text x="${x}" y="${y}" text-anchor="middle" class="rl">${esc(label)}</text>`; });
    scores.forEach((sc, j) => {
      const pts = sc.map((v, k) => v === null ? null : pt(k, v));
      svg += `<polygon class="rp s${j + 1}" points="${pts.filter(Boolean).map(p => p.join(",")).join(" ")}"/>`;
      pts.forEach(p => { if (p) svg += `<circle class="s${j + 1}" cx="${p[0]}" cy="${p[1]}" r="3"/>`; });
    });
    svg += "</svg>";
    const table = `<div class="table-wrap"><table><thead><tr><th>Theme</th>${ents.map((e, k) => `<th class="num"><i class="sw s${k + 1}"></i> ${esc(e.name)}</th>`).join("")}</tr></thead><tbody>${THEMES.map(([, l], k) => `<tr><td>${esc(l)}</td>${scores.map(sc => `<td class="num">${sc[k] === null ? '<span class="muted">—</span>' : Math.round(sc[k])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    return `<div class="grid g2 cmp-profile"><div class="card">${svg}</div><div>${table}
      <p class="small"><b>How this is normalised.</b> Each axis is the average of a country’s percentile ranks on that theme’s indicators: the share of countries with data that it does better than, from 0 to 100, so higher is always better. Indicators without a direction (such as population) are left out, and a theme needs at least three indicators with data, otherwise it shows “—” and the shape skips that axis. It is a quick profile, not an index.</p></div></div>`;
  }

  async function render() {
    const s = state();
    chips.innerHTML = s.c.map((id, k) => `<button type="button" class="chip-btn" data-rm="${id}" aria-label="Remove ${esc(idToName[id])}"><i class="sw s${k + 1}"></i> ${esc(idToName[id])} ✕</button>`).join("") ||
      '<span class="muted small">No countries selected.</span>';
    add.disabled = s.c.length >= 5; add.placeholder = s.c.length >= 5 ? "Five countries is the maximum" : "Type a country name…";
    document.querySelectorAll("[data-view]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === s.v)));
    if (s.c.length < 2) { out.innerHTML = '<p class="muted">Add at least two countries to start.</p>'; return; }
    out.innerHTML = '<p class="muted">Loading…</p>';
    const [[inds], ents] = await Promise.all([loadMeta(), Promise.all(s.c.map(load))]);
    out.innerHTML = s.v === "trends" ? trendsView(inds, ents, s.i) : s.v === "profile" ? profileView(inds, ents) : tableView(inds, ents);
    document.title = ents.map(e => e.name).join(" vs ") + " · Compare";
    document.getElementById("cmp-ind")?.addEventListener("change", e => setState({ i: e.target.value }, false));
    document.getElementById("cmp-csv")?.addEventListener("click", () => {
      const rows = [["Indicator", ...ents.flatMap(e => [e.name, e.name + " year", e.name + " source"])]];
      for (const ind of inds) rows.push([ind.name, ...ents.flatMap(e => { const v = e.latest[ind.indicator_id]; return v ? [String(v.value), String(v.year), v.source] : ["", "", ""]; })]);
      rows.push([], ["Source: " + location.href + " — CC BY 4.0; values keep their source licence."]);
      window.atlasCSV(rows, s.c.join("-vs-").toLowerCase() + ".csv");
    });
  }
  window.addEventListener("popstate", render);
  window.addEventListener("hashchange", render);
  if (!location.search && /c=/.test(location.hash)) setState({}, false); else render();
})();
