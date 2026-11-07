/* Explore page: choose an indicator (and year) and show it on the map. */
(() => {
  "use strict";
  const sel = document.getElementById("explore-ind");
  const yearSel = document.getElementById("explore-year");
  const link = document.getElementById("explore-link");
  const note = document.getElementById("explore-note");
  const mapEl = document.getElementById("explore-map");
  const cache = {};
  const SRC = { "un-wpp": "UN World Population Prospects 2024", "wb-wgi": "World Bank WGI", "wb-wdi": "World Bank WDI", "undp-hdr": "UNDP HDR 2025", "ti-cpi": "Transparency International", oecd: "OECD", gdelt: "GDELT" };

  if (location.hash.length > 1 && sel.querySelector(`option[value="${CSS.escape(location.hash.slice(1))}"]`)) {
    sel.value = location.hash.slice(1);
  }

  async function load(id) {
    if (!cache[id]) cache[id] = fetch(`/v1/latest/indicators/${id}.json`).then(r => r.json());
    return cache[id];
  }

  async function draw(resetYear) {
    const id = sel.value;
    const opt = sel.selectedOptions[0];
    const ind = await load(id);
    if (resetYear) {
      const years = Object.keys(ind.coverage_by_year).map(Number).filter(y => y >= 1990).sort((a, b) => b - a);
      yearSel.innerHTML = '<option value="latest">Latest available</option>' + years.map(y => `<option>${y}</option>`).join("");
    }
    const year = yearSel.value;
    const values = {}; let minY = 9999, maxY = 0, n = 0;
    for (const [e, rows] of Object.entries(ind.data)) {
      let hit = null;
      if (year === "latest") hit = rows[rows.length - 1];
      else hit = rows.find(r => r[0] === +year) || null;
      if (hit) { values[e] = hit[1]; minY = Math.min(minY, hit[0]); maxY = Math.max(maxY, hit[0]); n++; }
    }
    await window.atlasMap(mapEl, values, { lowerBetter: opt.dataset.lower === "1", label: ind.name });
    link.href = `/data/indicators/${id}/`;
    history.replaceState(null, "", "#" + id);
    note.textContent = `${ind.name} (${ind.unit}). ${n} countries` +
      (year === "latest" ? `, latest values from ${minY}–${maxY}.` : ` in ${year}.`) +
      ` Source: ${SRC[ind.source] || ind.source} (${ind.source_licence}). Colours are 7 equal-count groups` +
      (opt.dataset.lower === "1" ? "; darker is better (lower)." : "; darker is higher.");
  }
  sel.addEventListener("change", () => draw(true));
  yearSel.addEventListener("change", () => draw(false));
  draw(true);
})();
