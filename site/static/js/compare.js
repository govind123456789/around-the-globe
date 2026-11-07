/* Compare 2–5 countries client-side. State lives in the URL fragment: #c=IND,CHN */
(() => {
  "use strict";
  const ids = JSON.parse(document.getElementById("cmp-countries").textContent);
  const names = JSON.parse(document.getElementById("cmp-names").textContent);
  const nameToId = Object.fromEntries(names.map((n, i) => [n.toLowerCase(), ids[i]]));
  const idToName = Object.fromEntries(ids.map((id, i) => [id, names[i]]));
  const add = document.getElementById("cmp-add");
  const chips = document.getElementById("cmp-chips");
  const out = document.getElementById("cmp-out");
  const esc = window.atlasEsc, f = window.atlasFmt;
  const cache = {};
  let meta = null;

  const state = () => {
    const m = location.hash.match(/c=([A-Z,]+)/);
    return m ? [...new Set(m[1].split(",").filter(x => idToName[x]))].slice(0, 5) : [];
  };
  const setState = list => { location.hash = "c=" + list.join(","); };

  add.addEventListener("change", () => {
    const id = nameToId[add.value.trim().toLowerCase()];
    if (id) { const s = state(); if (!s.includes(id) && s.length < 5) setState([...s, id]); add.value = ""; }
  });
  chips.addEventListener("click", e => {
    const b = e.target.closest("[data-rm]"); if (b) setState(state().filter(x => x !== b.dataset.rm));
  });

  const load = id => cache[id] || (cache[id] = fetch(`/v1/latest/entities/country/${id}.json`).then(r => r.json()));
  const loadMeta = async () => meta || (meta = await Promise.all([
    fetch("/v1/latest/indicators.json").then(r => r.json()),
    fetch("/v1/latest/rankings.json").then(r => r.json()),
  ]));

  function fmtVal(v, ind) {
    if (v === undefined) return '<span class="muted">—</span>';
    const d = ind.decimals ?? 2;
    const num = Math.abs(v.value) >= 1e6 ? f(v.value) : v.value.toLocaleString("en", { maximumFractionDigits: d, minimumFractionDigits: d });
    return `${ind.unit.startsWith("current US$") && !ind.unit.endsWith("person") ? "$" : ""}${num} <span class="muted small">${v.year}</span>${v.status === "estimate" ? ' <span class="chip"><span class="st">EST</span></span>' : ""}`;
  }

  async function render() {
    const s = state();
    chips.innerHTML = s.map(id => `<a href="javascript:void 0" data-rm="${id}" title="Remove">${esc(idToName[id])} ✕</a>`).join("") ||
      '<span class="muted small">No countries selected.</span>';
    if (s.length < 2) { out.innerHTML = '<p class="muted">Add at least two countries to start.</p>'; return; }
    out.innerHTML = '<p class="muted">Loading…</p>';
    const [[inds, rks], ents] = await Promise.all([loadMeta(), Promise.all(s.map(load))]);
    const dims = [...new Set(inds.map(i => i.dimension))];
    const dimName = { economy: "Economy", human: "Human development", innovation: "Innovation & technology", health: "Health",
      education: "Education", environment: "Environment & energy", demography: "Demography", society: "Society & inclusion",
      governance: "Governance", media: "Media attention" };
    let html = `<h2>Rankings</h2><div class="table-wrap"><table><thead><tr><th>Ranking</th>${ents.map(e => `<th class="num">${window.atlasFlag(e.attributes && e.attributes.iso2)}<a href="/countries/${e.slug}/">${esc(e.name)}</a></th>`).join("")}</tr></thead><tbody>`;
    for (const r of rks) {
      html += `<tr><td><a href="/rankings/${r.ranking_id}/">${esc(r.name)}</a></td>` + ents.map(e => {
        const p = e.rankings.find(x => x.ranking_id === r.ranking_id);
        return `<td class="num">${p && p.rank ? `<b>${p.is_tied ? "=" : ""}${p.rank}</b> <span class="muted small">of ${p.of}</span>` : '<span class="muted small">Not ranked</span>'}</td>`;
      }).join("") + "</tr>";
    }
    html += "</tbody></table></div>";
    const chartInds = ["gdp-per-capita-ppp", "hdi", "life-expectancy", "internet-users"];
    html += '<h2>Trends</h2><div class="grid g2">' + chartInds.map(id => {
      const ind = inds.find(i => i.indicator_id === id);
      const series = ents.map(e => ({ label: e.name, points: e.series[id] || [] }));
      return `<div class="card"><h3><a href="/data/indicators/${id}/">${esc(ind.name)}</a> <span class="muted small">${esc(ind.unit)}</span></h3>${window.atlasLineChart(series, { title: ind.name })}</div>`;
    }).join("") + "</div>";
    html += `<h2>All indicators</h2><div class="btns" style="margin-bottom:10px"><button class="btn ghost sm" id="cmp-csv">Download CSV</button></div><div class="table-wrap"><table id="cmp-table"><thead><tr><th>Indicator</th>${ents.map(e => `<th class="num">${esc(e.name)}</th>`).join("")}</tr></thead>`;
    for (const d of dims) {
      const rows = inds.filter(i => i.dimension === d && ents.some(e => e.latest[i.indicator_id]));
      if (!rows.length) continue;
      html += `<tbody><tr><th colspan="${ents.length + 1}" style="position:static">${dimName[d] || d}</th></tr>`;
      for (const ind of rows) {
        const years = new Set(ents.map(e => e.latest[ind.indicator_id]?.year).filter(Boolean));
        html += `<tr><td><a href="/data/indicators/${ind.indicator_id}/">${esc(ind.name)}</a>${years.size > 1 ? ' <span class="small stale" title="Values are from different years">⚠ years differ</span>' : ""}</td>` +
          ents.map(e => `<td class="num">${fmtVal(e.latest[ind.indicator_id], ind)}</td>`).join("") + "</tr>";
      }
      html += "</tbody>";
    }
    html += '</table></div><p class="small muted" style="margin-top:8px">Sources: World Bank WDI, OECD, Transparency International (CC BY 4.0), UNDP HDR 2025 (CC BY 3.0 IGO), GDELT. Small numbers are data years.</p>';
    out.innerHTML = html;
    document.title = ents.map(e => e.name).join(" vs ") + " · Compare";
    document.getElementById("cmp-csv").addEventListener("click", () => {
      const rows = [["Indicator", ...ents.flatMap(e => [e.name, e.name + " year"])]];
      for (const ind of inds) rows.push([ind.name, ...ents.flatMap(e => { const v = e.latest[ind.indicator_id]; return v ? [String(v.value), String(v.year)] : ["", ""]; })]);
      rows.push([], ["Source: " + location.href + " — CC BY 4.0; values keep their source licence."]);
      window.atlasCSV(rows, s.join("-vs-") + ".csv");
    });
  }
  window.addEventListener("hashchange", render);
  render();
})();
