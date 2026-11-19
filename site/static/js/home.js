/* Homepage map: switch between headline indicators. The interactive map re-colours in place; the static
   map (phones, or before it loads) is re-coloured with the same seven quantile bins as the server. */
(() => {
  const data = document.getElementById("hero-maps"), el = document.getElementById("home-map");
  if (!data || !el) return;
  const maps = JSON.parse(data.textContent), box = el.closest(".map-box");
  const fmt = v => NF.label(v);
  function bins(values, lower) {
    const vals = Object.values(values).filter(v => v !== null && isFinite(v)).sort((a, b) => a - b);
    if (!vals.length) return {};
    const br = [1, 2, 3, 4, 5, 6].map(i => vals[Math.floor(i / 7 * (vals.length - 1))]), out = {};
    for (const [k, v] of Object.entries(values)) { let b = 0; while (b < 6 && v > br[b]) b++; out[k] = lower ? 6 - b : b; }
    return out;
  }
  function show(i) {
    const m = maps[i];
    document.querySelectorAll("[data-map-pick]").forEach(b => b.setAttribute("aria-pressed", String(+b.dataset.mapPick === i)));
    document.querySelector("[data-map-title]").textContent = m.label;
    el.setAttribute("aria-label", `World map: ${m.label}, ${Object.keys(m.values).length} countries with data`);
    box.querySelector("[data-map-values]").textContent = JSON.stringify(m.values);
    const vals = Object.values(m.values), lo = Math.min(...vals), hi = Math.max(...vals);
    const loEl = box.querySelector("[data-lo]"), hiEl = box.querySelector("[data-hi]");
    if (loEl) loEl.textContent = fmt(m.lower ? hi : lo);
    if (hiEl) hiEl.textContent = fmt(m.lower ? lo : hi) + (m.lower ? " (better)" : "");
    if (el._map && window.atlasMap) { window.atlasMap(el, m.values, { lowerBetter: m.lower, label: m.label }); return; }
    const b = bins(m.values, m.lower);
    el.querySelectorAll(".map-static use").forEach(u => { const iso = (u.getAttribute("href") || "").split("#c-")[1]; u.setAttribute("class", iso in b ? "m" + b[iso] : "mna"); });
    el._values = m.values; el._lowerBetter = m.lower; el._label = m.label;
  }
  document.querySelector(".map-pick")?.addEventListener("click", e => { const b = e.target.closest("[data-map-pick]"); if (b) show(+b.dataset.mapPick); });
})();
