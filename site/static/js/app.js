/* Shared behaviour for every page: theme, menu, search, tables, CSV, share, maps. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };

  // ---------- theme ----------
  $("#theme-toggle")?.addEventListener("click", () => {
    const root = document.documentElement;
    const dark = root.dataset.theme ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    store.set("theme", root.dataset.theme);
    document.dispatchEvent(new Event("themechange"));
  });

  // ---------- mobile menu ----------
  const menuBtn = $("#menu-btn");
  menuBtn?.addEventListener("click", () => {
    const open = $("#nav").classList.toggle("open");
    menuBtn.setAttribute("aria-expanded", open);
  });

  window.atlasFlag = iso2 => iso2 ? `<img class="flag" src="/static/flags/${esc(iso2.toLowerCase())}.svg" width="20" height="15" alt="" loading="lazy" onerror="this.remove()">` : "";

  // ---------- question tabs ----------
  $$("[data-tabs]").forEach(bar => {
    const tabs = $$('[role="tab"]', bar);
    const show = tab => {
      tabs.forEach(t => {
        const on = t === tab;
        t.setAttribute("aria-selected", on);
        on ? t.removeAttribute("tabindex") : t.setAttribute("tabindex", "-1");
        document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
      });
    };
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => show(t));
      t.addEventListener("keydown", e => {
        const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; show(n); n.focus(); e.preventDefault(); }
      });
    });
    bar.classList.add("ready");
    show(tabs[0]);
  });

  // ---------- search ----------
  let index = null;
  const loadIndex = () => index || (index = fetch("/search-index.json").then(r => r.json()));
  window.atlasIndex = loadIndex;
  const norm = s => s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");

  function score(item, q) {
    let best = scoreText(item, norm(item.t), q);
    for (const alias of item.o || []) best = Math.max(best, scoreText(item, norm(alias), q) - 5);
    return Math.max(best, 0);
  }
  function scoreText(item, t, q) {
    if (t === q || (item.a && item.a.toLowerCase() === q)) return 100;
    if (t.startsWith(q)) return 80;
    if (t.split(/[\s,()-]+/).some(w => w.startsWith(q))) return 60;
    if (t.includes(q)) return 40;
    // tolerate one typo for longer queries
    if (q.length > 3) {
      for (const w of t.split(/\s+/)) if (Math.abs(w.length - q.length) <= 1 && lev(w, q) <= 1) return 30;
    }
    return 0;
  }
  function lev(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  }
  function bestCountry(items, q) {
    let best = null, bs = 0;
    for (const it of items) if (it.k === "Country") { const s = score(it, q); if (s > bs) { bs = s; best = it; } }
    return bs >= 30 ? best : null;
  }
  function search(items, raw) {
    const q = norm(raw.trim());
    if (!q) return [];
    const vs = q.split(/\s+(?:vs\.?|versus|v)\s+|\s*,\s*/).filter(Boolean);
    const out = [];
    if (vs.length >= 2) {
      const cs = vs.map(v => bestCountry(items, v)).filter(Boolean);
      if (cs.length >= 2) out.push({ t: cs.map(c => c.t).join(" vs "), u: "/compare/#c=" + cs.map(c => c.a).join(","), k: "Compare" });
    }
    return out.concat(items.map(it => [score(it, q), it]).filter(x => x[0] > 0)
      .sort((a, b) => b[0] - a[0] || a[1].t.length - b[1].t.length).slice(0, 12).map(x => x[1]));
  }
  function wire(input) {
    const box = input.parentElement.querySelector(".search-results");
    let sel = -1, hits = [];
    const draw = () => {
      box.innerHTML = hits.map((h, i) => `<a href="${h.u}" role="option"${i === sel ? ' class="sel" aria-selected="true"' : ""}><span>${h.f ? window.atlasFlag(h.f) : ""}${esc(h.t)}</span><span class="k">${esc(h.k)}${h.s ? " · " + esc(h.s) : ""}</span></a>`).join("")
        || (input.value.trim() ? '<a aria-disabled="true"><span class="muted">No matches</span></a>' : "");
      box.classList.toggle("open", !!input.value.trim());
    };
    input.addEventListener("focus", loadIndex, { once: true });
    input.addEventListener("input", async () => { hits = search(await loadIndex(), input.value); sel = -1; draw(); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { sel = Math.min(sel + 1, hits.length - 1); draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
      else if (e.key === "Enter") { const h = hits[sel] || hits[0]; if (h) location.href = h.u; }
      else if (e.key === "Escape") { box.classList.remove("open"); }
    });
    document.addEventListener("click", e => { if (!input.parentElement.contains(e.target)) box.classList.remove("open"); });
  }
  $$("[data-search]").forEach(wire);
  const dlg = $("#search-dialog");
  const openSearch = () => { dlg.showModal(); $("input", dlg).focus(); };
  $("#search-open")?.addEventListener("click", openSearch);
  document.addEventListener("keydown", e => {
    if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); openSearch(); }
  });
  dlg?.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });

  // ---------- sortable tables ----------
  function sortTable(table, th) {
    const idx = Array.from(th.parentElement.children).indexOf(th);
    const num = th.dataset.type === "num";
    const asc = th.getAttribute("aria-sort") !== "ascending";
    $$("th", th.parentElement).forEach(h => h.removeAttribute("aria-sort"));
    th.setAttribute("aria-sort", asc ? "ascending" : "descending");
    const body = table.tBodies[0];
    const rows = Array.from(body.rows);
    const key = r => {
      const c = r.cells[idx]; const v = c?.dataset.v ?? c?.textContent.trim() ?? "";
      if (!num) return v.toLowerCase();
      return v === "" ? null : parseFloat(v);
    };
    rows.sort((a, b) => {
      const x = key(a), y = key(b);
      if (x === null) return 1; if (y === null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
    });
    rows.forEach(r => body.appendChild(r));
  }
  window.atlasSortable = table => $$("th.sortable", table).forEach(th => {
    th.tabIndex = 0;
    th.addEventListener("click", () => sortTable(table, th));
    th.addEventListener("keydown", e => { if (e.key === "Enter") sortTable(table, th); });
  });
  $$("table[data-sortable]").forEach(window.atlasSortable);

  // ---------- ranking filters ----------
  $$("[data-filters]").forEach(bar => {
    const table = document.getElementById(bar.dataset.filters);
    const text = $("[data-f-text]", bar), region = $("[data-f-region]", bar), income = $("[data-f-income]", bar),
      ranked = $("[data-f-ranked]", bar), count = $("[data-f-count]", bar);
    const apply = () => {
      const q = (text.value || "").toLowerCase(); let n = 0;
      for (const r of table.tBodies[0].rows) {
        const show = (!q || r.dataset.name.includes(q)) && (!region.value || r.dataset.region === region.value)
          && (!income.value || r.dataset.income === income.value) && (!ranked.checked || !("unranked" in r.dataset));
        r.hidden = !show; if (show) n++;
      }
      count.textContent = `${n} shown`;
    };
    [text, region, income, ranked].forEach(el => el.addEventListener("input", apply));
    apply();
  });

  // ---------- list filters ----------
  $$("[data-filter-list]").forEach(inp => {
    const root = $(inp.dataset.filterList);
    inp.addEventListener("input", () => {
      const q = inp.value.toLowerCase();
      $$("[data-item]", root).forEach(el => { el.hidden = q && !el.dataset.item.includes(q); });
      $$("[data-group]", root).forEach(g => { g.hidden = !$$("[data-item]", g).some(el => !el.hidden); });
    });
  });

  // ---------- CSV export of a visible table ----------
  window.atlasCSV = (rows, name) => {
    const csv = rows.map(r => r.map(c => /[",\n]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  $$("[data-csv]").forEach(btn => btn.addEventListener("click", () => {
    const t = document.getElementById(btn.dataset.csv);
    const rows = Array.from(t.rows).filter(r => !r.hidden).map(r => Array.from(r.cells).map(c => c.textContent.replace(/\s+/g, " ").trim()));
    rows.push([], [`Source: ${location.href} — licence CC BY 4.0; source values keep their source licence.`]);
    window.atlasCSV(rows, btn.dataset.csvName || "table.csv");
  }));

  // ---------- share ----------
  $$("[data-share]").forEach(btn => btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(location.href); btn.textContent = "Link copied"; }
    catch (e) { prompt("Copy this link:", location.href); }
  }));

  // ---------- copy embed code ----------
  $$("[data-copy]").forEach(btn => btn.addEventListener("click", async () => {
    const label = btn.textContent;
    try { await navigator.clipboard.writeText(btn.dataset.copy); btn.textContent = "Embed code copied"; setTimeout(() => { btn.textContent = label; }, 2000); }
    catch (e) { prompt("Copy this embed code:", btn.dataset.copy); }
  }));

  // ---------- compare form (home) ----------
  $$("[data-compare-form]").forEach(f => f.addEventListener("submit", e => {
    e.preventDefault();
    location.href = `/compare/#c=${f.a.value},${f.b.value}`;
  }));

  // ---------- maps ----------
  const MAPLIBRE = "/static/vendor/maplibre-gl";
  let libPromise = null, geoPromise = null;
  function loadLib() {
    if (libPromise) return libPromise;
    const css = document.createElement("link"); css.rel = "stylesheet"; css.href = MAPLIBRE + ".css";
    document.head.appendChild(css);
    libPromise = new Promise((res, rej) => {
      const s = document.createElement("script"); s.src = MAPLIBRE + ".js"; s.onload = () => res(window.maplibregl); s.onerror = rej;
      document.head.appendChild(s);
    });
    return libPromise;
  }
  const loadGeo = () => geoPromise || (geoPromise = fetch("/geo/countries.json").then(r => r.json()));
  const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmtNum = v => {
    const a = Math.abs(v);
    if (a >= 1e12) return (v / 1e12).toFixed(1) + " tn"; if (a >= 1e9) return (v / 1e9).toFixed(1) + " bn";
    if (a >= 1e6) return (v / 1e6).toFixed(1) + " m"; if (a >= 1e4) return Math.round(v / 1e3) + "k";
    if (a >= 100) return Math.round(v).toLocaleString("en"); return (+v.toFixed(2)).toString();
  };
  window.atlasFmt = fmtNum;

  function colorExpr(values, lowerBetter) {
    const vals = Object.values(values).filter(v => v !== null && isFinite(v)).sort((a, b) => a - b);
    const ramp = [0, 1, 2, 3, 4, 5, 6].map(i => cssVar(`--map-${i}`));
    const na = cssVar("--map-na");
    if (!vals.length) return { expr: na, lo: null, hi: null };
    const breaks = [1, 2, 3, 4, 5, 6].map(i => vals[Math.floor(i / 7 * (vals.length - 1))]);
    const bin = v => { let b = 0; while (b < 6 && v > breaks[b]) b++; return lowerBetter ? 6 - b : b; };
    const expr = ["match", ["get", "iso3"]];
    for (const [k, v] of Object.entries(values)) if (v !== null && isFinite(v)) expr.push(k, ramp[bin(v)]);
    expr.push(na);
    return { expr: expr.length > 3 ? expr : na, lo: vals[0], hi: vals[vals.length - 1] };
  }

  async function renderMap(el, values, opts = {}) {
    const box = el.closest(".map-box");
    const tip = $(".map-tip", box);
    const lowerBetter = opts.lowerBetter ?? ("lowerBetter" in el.dataset);
    const label = opts.label || el.dataset.label || "";
    el._values = values; el._lowerBetter = lowerBetter; el._label = label; el._unit = opts.unit || "";
    const [lib, geo, idx] = await Promise.all([loadLib(), loadGeo(), loadIndex()]);
    const urls = {}; idx.forEach(i => { if (i.a) urls[i.a] = i.u; });
    const { expr, lo, hi } = colorExpr(values, lowerBetter);
    const [loEl, hiEl] = [$("[data-lo]", box), $("[data-hi]", box)];
    if (loEl) loEl.textContent = lo === null ? "" : (lowerBetter ? fmtNum(hi) : fmtNum(lo));
    if (hiEl) hiEl.textContent = hi === null ? "" : (lowerBetter ? fmtNum(lo) + " (better)" : fmtNum(hi));
    if (el._map) {
      el._map.setPaintProperty("fill", "fill-color", expr);
      el._map.setPaintProperty("bg", "background-color", cssVar("--surface"));
      el._map.setPaintProperty("line", "line-color", cssVar("--surface"));
      return;
    }
    const map = new lib.Map({
      container: el, attributionControl: { compact: true, customAttribution: "Natural Earth" },
      style: { version: 8, sources: { c: { type: "geojson", data: geo } }, layers: [
        { id: "bg", type: "background", paint: { "background-color": cssVar("--surface") } },
        { id: "fill", type: "fill", source: "c", paint: { "fill-color": expr } },
        { id: "line", type: "line", source: "c", paint: { "line-color": cssVar("--surface"), "line-width": 0.6 } },
      ] },
      bounds: [[-165, -56], [180, 76]], renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
      cooperativeGestures: true, minZoom: 0.3, maxZoom: 6,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new lib.NavigationControl({ showCompass: false }), "top-right");
    el._map = map;
    map.on("mousemove", "fill", e => {
      const p = e.features[0].properties; const v = el._values[p.iso3];
      tip.style.display = "block";
      tip.style.left = Math.min(e.point.x + 14, el.clientWidth - 180) + "px"; tip.style.top = (e.point.y + 14) + "px";
      tip.innerHTML = `<b>${esc(p.name)}</b><br>${v === undefined || v === null ? '<span class="muted">No data</span>' : esc(el._label) + ": " + fmtNum(v)}`;
      map.getCanvas().style.cursor = urls[p.iso3] ? "pointer" : "";
    });
    map.on("mouseleave", "fill", () => { tip.style.display = "none"; map.getCanvas().style.cursor = ""; });
    map.on("click", "fill", e => { const u = urls[e.features[0].properties.iso3]; if (u) location.href = u; });
  }
  window.atlasMap = renderMap;
  const io = "IntersectionObserver" in window ? new IntersectionObserver(entries => entries.forEach(en => {
    if (!en.isIntersecting) return; io.unobserve(en.target);
    const json = $("[data-map-values]", en.target.closest(".map-box"));
    renderMap(en.target, JSON.parse(json.textContent)).catch(err => {
      en.target.innerHTML = '<p class="muted" style="padding:16px">The map could not load. Data is in the table.</p>'; console.error(err);
    });
  }), { rootMargin: "200px" }) : null;
  $$("[data-map]").forEach(el => { if (el.id !== "explore-map") io?.observe(el); });
  document.addEventListener("themechange", () => $$("[data-map]").forEach(el => { if (el._map) renderMap(el, el._values, { lowerBetter: el._lowerBetter, label: el._label }); }));

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  window.atlasEsc = esc;
})();
