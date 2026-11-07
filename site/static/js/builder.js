/* Index Builder: runs AtlasEngine over /v1/latest/matrix.json entirely in the browser.
   State is kept in the URL fragment so a link reproduces the index exactly. */
(() => {
  "use strict";
  const E = window.AtlasEngine, esc = window.atlasEsc;
  const $ = id => document.getElementById(id);
  const cap = JSON.parse($("ib-cap").textContent);
  const dims = JSON.parse($("ib-dims").textContent);
  const dimName = Object.fromEntries(dims.map(d => [d.id, d.name]));
  const capRank = Object.fromEntries(cap.ranks.map((e, i) => [e, i + 1]));

  const compPillars = JSON.parse($("ib-composites").textContent);
  const compIds = JSON.parse($("ib-composite-ids").textContent);
  const fromPillars = ps => ({ pillars: ps.map(p => ({ id: p.id, name: p.name, w: p.weight * 100, inds: p.indicators.map(i => ({ id: i.id, w: i.weight * 100 })) })) });
  const TEMPLATES = {
    capability: { pillars: cap.pillars.map(p => ({ id: p.id, name: p.name, w: p.weight * 100, inds: p.indicators.map(i => ({ id: i.id, w: i.weight * 100 })) })) },
    study: { pillars: [
      { id: "education", name: "Education", w: 50, inds: [{ id: "tertiary-enrolment", w: 40 }, { id: "education-spending", w: 30 }, { id: "researchers", w: 30 }] },
      { id: "living", name: "Living", w: 30, inds: [{ id: "life-expectancy", w: 50 }, { id: "pm25", w: 25 }, { id: "internet-users", w: 25 }] },
      { id: "economy", name: "Economy", w: 20, inds: [{ id: "gdp-per-capita-ppp", w: 60 }, { id: "unemployment", w: 40 }] } ] },
    relocation: { pillars: [
      { id: "economy", name: "Economy", w: 40, inds: [{ id: "gdp-per-capita-ppp", w: 50 }, { id: "unemployment", w: 25 }, { id: "inflation", w: 25 }] },
      { id: "health", name: "Health", w: 30, inds: [{ id: "life-expectancy", w: 40 }, { id: "physicians", w: 30 }, { id: "health-spending", w: 30 }] },
      { id: "environment", name: "Environment", w: 30, inds: [{ id: "pm25", w: 60 }, { id: "renewable-share", w: 40 }] } ] },
    market: { pillars: [
      { id: "size", name: "Market size", w: 50, inds: [{ id: "gdp", w: 40 }, { id: "population", w: 30 }, { id: "gdp-growth", w: 30 }] },
      { id: "openness", name: "Openness", w: 30, inds: [{ id: "exports-gdp", w: 50 }, { id: "fdi-inflows", w: 50 }] },
      { id: "connectivity", name: "Connectivity", w: 20, inds: [{ id: "internet-users", w: 50 }, { id: "electricity-access", w: 50 }] } ] },
    green: { pillars: [
      { id: "environment", name: "Environment", w: 70, inds: [{ id: "co2-per-capita", w: 30 }, { id: "renewable-share", w: 30 }, { id: "pm25", w: 20 }, { id: "forest-area", w: 20 }] },
      { id: "economy", name: "Economy", w: 30, inds: [{ id: "gdp-per-capita-ppp", w: 100 }] } ] },
    clear: { pillars: [] },
  };

  compIds.forEach((id, i) => { TEMPLATES[id] = fromPillars(compPillars[i]); });
  TEMPLATES.capability = TEMPLATES["capability-index"] || TEMPLATES.capability;
  let M = null, indById = {}, state = null, lastResults = [], lastInput = null, stabilityTimer = null;

  // ---------- state <-> URL ----------
  function encode(s) {
    const p = s.pillars.map(p => `${p.id}~${encodeURIComponent(p.name)}~${Math.round(p.w)};` + p.inds.map(i => `${i.id}:${Math.round(i.w)}`).join(",")).join("|");
    return `n=${s.norm}&a=${s.agg}&c=${s.cov}&m=${s.pop}&p=${p}`;
  }
  function decode(h) {
    const q = new URLSearchParams(h.replace(/^#/, ""));
    if (q.get("from")) return { ...defaults(), ...clone(TEMPLATES[q.get("from")] || TEMPLATES.capability) };
    if (!q.get("p") && !q.has("p")) return null;
    const pillars = (q.get("p") || "").split("|").filter(Boolean).map(seg => {
      const [head, list = ""] = seg.split(";"); const [id, name, w] = head.split("~");
      return { id, name: decodeURIComponent(name || id), w: +w || 0, inds: list.split(",").filter(Boolean).map(x => { const [i, ww] = x.split(":"); return { id: i, w: +ww || 0 }; }).filter(i => indById[i.id]) };
    });
    return { norm: q.get("n") || "min_max", agg: q.get("a") || "arithmetic", cov: +(q.get("c") || 0.7), pop: +(q.get("m") || 500000), pillars };
  }
  const defaults = () => ({ norm: "min_max", agg: "arithmetic", cov: 0.7, pop: 500000 });
  const clone = o => JSON.parse(JSON.stringify(o));

  // ---------- compute ----------
  function compute() {
    const ents = M.entities.filter((e, k) => (M.population[k] ?? 0) >= state.pop);
    const specs = [], pillars = [], norm = {};
    for (const p of state.pillars) {
      const inds = p.inds.filter(i => i.w > 0);
      if (!inds.length || p.w <= 0) continue;
      pillars.push({ id: p.id, weight: p.w });
      for (const i of inds) {
        const meta = indById[i.id], col = meta._col, vals = {};
        M.entities.forEach((e, k) => { const v = M.values[k][col]; if (v !== null && ents.includes(e)) vals[e] = v; });
        specs.push({ id: i.id, weight: i.w, pillar: p.id });
        norm[i.id] = E.normalise(vals, state.norm, meta.direction, meta.transform);
      }
    }
    if (!specs.length) { lastInput = null; return []; }
    lastInput = { norm, specs, pillars, ents };
    return E.score(norm, specs, pillars, ents, state.cov, state.agg);
  }

  // ---------- render ----------
  function renderPanel() {
    const box = $("ib-weights");
    if (!state.pillars.length) { box.innerHTML = '<p class="small muted">No indicators yet. Add some below, or start from a template.</p>'; }
    else box.innerHTML = state.pillars.map((p, pi) => `
      <div class="wrow" style="border-bottom:1px solid var(--border-strong)"><b>${esc(p.name)}</b>
        <input type="range" min="0" max="100" value="${p.w}" data-pw="${pi}" aria-label="${esc(p.name)} pillar weight">
        <span class="w">${Math.round(p.w)}</span></div>` +
      p.inds.map((i, ii) => `
      <div class="wrow" style="padding-left:12px"><span>${esc(indById[i.id].name)}${indById[i.id].direction === "lower_better" ? ' <span class="muted small">↓</span>' : ""}</span>
        <input type="range" min="0" max="100" value="${i.w}" data-iw="${pi}:${ii}" aria-label="${esc(indById[i.id].name)} weight">
        <button class="x" data-rm="${pi}:${ii}" aria-label="Remove ${esc(indById[i.id].name)}">✕</button></div>`).join("")).join("");
    const used = new Set(state.pillars.flatMap(p => p.inds.map(i => i.id)));
    const groups = {};
    for (const i of M.indicators) (groups[i.dimension] = groups[i.dimension] || []).push(i);
    $("ib-picker").innerHTML = Object.entries(groups).map(([d, list]) => `<div class="dim">${esc(dimName[d] || d)}</div>` +
      list.map(i => `<label><input type="checkbox" data-add="${i.indicator_id}"${used.has(i.indicator_id) ? " checked" : ""}> ${esc(i.name)}</label>`).join("")).join("");
    const tw = state.pillars.reduce((a, p) => a + p.w, 0);
    $("ib-sum").textContent = state.pillars.length ? "Pillar weights: " + state.pillars.map(p => `${p.name} ${tw ? Math.round(p.w / tw * 100) : 0}%`).join(" · ") + " (weights are relative and are normalised automatically)" : "";
    ["norm", "agg", "cov", "pop"].forEach(k => { $("ib-" + k).value = String(state[k]); });
  }

  function renderResults() {
    const res = compute(); lastResults = res;
    const name = Object.fromEntries(M.entities.map((e, k) => [e, M.names[k]]));
    const slug = Object.fromEntries(M.entities.map((e, k) => [e, M.slugs[k]]));
    const iso2 = Object.fromEntries(M.entities.map((e, k) => [e, M.iso2[k]]));
    const ranked = res.filter(r => r.rank);
    const tbody = $("ib-table").tBodies[0];
    tbody.innerHTML = res.map(r => {
      const d = r.rank && capRank[r.entity_id] ? capRank[r.entity_id] - r.rank : null;
      return `<tr${r.rank ? "" : ' class="excluded"'}><td class="num rank" data-v="${r.rank || 9999}">${r.rank ? (r.is_tied ? "=" : "") + r.rank : "—"}</td>
        <td>${window.atlasFlag(iso2[r.entity_id])}<a href="/countries/${slug[r.entity_id]}/">${esc(name[r.entity_id])}</a>${r.rank ? "" : ' <span class="muted small">· insufficient data</span>'}</td>
        <td class="num" data-v="${r.score ?? ""}"><b>${r.score === null ? "—" : r.score.toFixed(1)}</b></td>
        <td class="num" data-v="${r.coverage}">${Math.round(r.coverage * 100)}%</td>
        <td class="num small" data-band="${r.entity_id}"></td>
        <td class="small">${d === null ? '<span class="muted">·</span>' : d > 0 ? `<span class="mv up">▲${d}</span>` : d < 0 ? `<span class="mv down">▼${-d}</span>` : '<span class="muted">=</span>'}</td></tr>`;
    }).join("");
    const top = ranked.slice(0, 3).map(r => esc(name[r.entity_id])).join(", ");
    $("ib-summary").innerHTML = ranked.length
      ? `<b>${ranked.length}</b> countries ranked, <b>${res.length - ranked.length}</b> without enough data (coverage below ${Math.round(state.cov * 100)}%). Top 3: ${top}. Data: latest value ${M.reference_year - M.max_data_age}–${M.reference_year}, release ${esc(M.release)}.`
      : "Add indicators with a weight above zero to build an index.";
    scheduleStability();
  }

  /* Rank ranges take a moment to compute, so they run shortly after the sliders stop moving. */
  function scheduleStability() {
    clearTimeout(stabilityTimer);
    const note = $("ib-stability");
    note.textContent = lastInput ? "Testing how stable these ranks are…" : "";
    if (!lastInput) return;
    stabilityTimer = setTimeout(() => {
      const { norm, specs, pillars, ents } = lastInput;
      const runs = 200, bands = E.sensitivity(norm, specs, pillars, ents, state.cov, state.agg, runs, 0.25, 20261107);
      let stable = 0;
      const top = lastResults.filter(r => r.rank).slice(0, 10);
      for (const r of top) if (bands[r.entity_id] && bands[r.entity_id][1] <= 10) stable++;
      for (const td of document.querySelectorAll("[data-band]")) {
        const b = bands[td.dataset.band];
        td.textContent = b ? `${b[0]}–${b[1]}` : "";
        td.dataset.v = b ? b[1] - b[0] : "";
      }
      const widths = Object.values(bands).map(b => b[1] - b[0]).sort((a, b) => a - b);
      const median = widths[Math.floor(widths.length / 2)] || 0;
      note.textContent = `Stability: ${stable} of the top ${top.length} stay in the top 10 when every weight shifts by up to ±25% (${runs} random tests). The typical country’s rank moves across ${median} places.`;
    }, 350);
  }

  function update(push = true) {
    renderPanel(); renderResults();
    if (push) history.replaceState(null, "", "#" + encode(state));
  }

  // ---------- events ----------
  $("ib-panel").addEventListener("input", e => {
    const t = e.target;
    if (t.dataset.pw !== undefined) { state.pillars[+t.dataset.pw].w = +t.value; t.nextElementSibling.textContent = t.value; renderResults(); history.replaceState(null, "", "#" + encode(state)); }
    else if (t.dataset.iw !== undefined) { const [p, i] = t.dataset.iw.split(":").map(Number); state.pillars[p].inds[i].w = +t.value; renderResults(); history.replaceState(null, "", "#" + encode(state)); }
  });
  $("ib-panel").addEventListener("change", e => {
    const t = e.target;
    if (t.dataset.add !== undefined) {
      const id = t.dataset.add, d = indById[id].dimension;
      if (t.checked) {
        let p = state.pillars.find(p => p.id === d);
        if (!p) { p = { id: d, name: dimName[d] || d, w: 30, inds: [] }; state.pillars.push(p); }
        p.inds.push({ id, w: 50 });
      } else {
        state.pillars.forEach(p => { p.inds = p.inds.filter(i => i.id !== id); });
        state.pillars = state.pillars.filter(p => p.inds.length);
      }
      update();
    } else if (["ib-norm", "ib-agg", "ib-cov", "ib-pop"].includes(t.id)) {
      const k = t.id.slice(3); state[k] = ["cov", "pop"].includes(k) ? +t.value : t.value; update();
    }
  });
  $("ib-panel").addEventListener("click", e => {
    const rm = e.target.closest("[data-rm]");
    if (rm) { const [p, i] = rm.dataset.rm.split(":").map(Number); state.pillars[p].inds.splice(i, 1); state.pillars = state.pillars.filter(p => p.inds.length); update(); }
    const tpl = e.target.closest("[data-tpl]");
    if (tpl) { state = { ...defaults(), ...clone(TEMPLATES[tpl.dataset.tpl]) }; update(); }
  });
  $("ib-copy").addEventListener("click", async e => {
    try { await navigator.clipboard.writeText(location.href); e.target.textContent = "Link copied"; } catch (err) { prompt("Copy this link:", location.href); }
  });
  $("ib-csv").addEventListener("click", () => {
    const name = Object.fromEntries(M.entities.map((e, k) => [e, M.names[k]]));
    const rows = [["rank", "entity_id", "country", "score", "coverage"]];
    for (const r of lastResults) rows.push([r.rank ? String(r.rank) : "", r.entity_id, name[r.entity_id], r.score === null ? "" : r.score.toFixed(4), r.coverage.toFixed(3)]);
    rows.push([]);
    rows.push(["# Custom index built at " + location.href]);
    rows.push(["# Indicators: " + state.pillars.flatMap(p => p.inds.map(i => `${indById[i.id].name} [${indById[i.id].source}, ${indById[i.id].source_licence}]`)).join("; ")]);
    rows.push(["# This index inherits its sources' licences (see the indicator list above; World Bank and OECD CC BY 4.0, UNDP HDR CC BY 3.0 IGO). It is not an official ranking."]);
    window.atlasCSV(rows, "custom-index.csv");
  });

  // ---------- boot ----------
  fetch("/v1/latest/matrix.json").then(r => r.json()).then(m => {
    M = m;
    M.indicators.forEach((i, k) => { i._col = k; i.id = i.indicator_id; indById[i.indicator_id] = i; });
    state = decode(location.hash) || { ...defaults(), ...clone(TEMPLATES.capability) };
    update(false);
  }).catch(err => { $("ib-summary").textContent = "Could not load the data matrix."; console.error(err); });
})();
