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
  const menuBtn = $("#menu-btn"), nav = $("#nav");
  const setDrawer = open => {
    nav.classList.toggle("open", open); document.documentElement.classList.toggle("drawer-open", open);
    menuBtn.setAttribute("aria-expanded", open); menuBtn.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    menuBtn.textContent = open ? "✕" : "☰";
    if (open) $(".nav-btn", nav)?.focus();
  };
  menuBtn?.addEventListener("click", () => setDrawer(!nav.classList.contains("open")));
  // menus: disclosure buttons (no hover-only opening); one open at a time
  const closeMenu = (btn, focus) => { btn.setAttribute("aria-expanded", "false"); document.getElementById(btn.getAttribute("aria-controls")).hidden = true; if (focus) btn.focus(); };
  $$(".nav-btn").forEach(btn => btn.addEventListener("click", () => {
    const open = btn.getAttribute("aria-expanded") === "true";
    $$(".nav-btn[aria-expanded='true']").forEach(o => { if (o !== btn) closeMenu(o); });
    if (open) closeMenu(btn); else { btn.setAttribute("aria-expanded", "true"); document.getElementById(btn.getAttribute("aria-controls")).hidden = false; }
  }));
  document.addEventListener("click", e => { if (!e.target.closest(".nav-item")) $$(".nav-btn[aria-expanded='true']").forEach(b => closeMenu(b)); });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    const openBtn = $(".nav-btn[aria-expanded='true']");
    if (openBtn) { closeMenu(openBtn, true); return; }
    if (nav?.classList.contains("open")) { setDrawer(false); menuBtn.focus(); }
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
    // several words in any order: "sudan war", "india exports", "nato members"
    const words = q.split(/\s+/).filter(w => w.length > 1);
    if (best < 35 && words.length > 1) {
      const hay = norm([item.t, item.s || "", item.k || "", ...(item.o || [])].join(" "));
      const hayWords = hay.split(/[\s,()·-]+/);
      const hit = w => hay.includes(w) || (w.length > 4 && hayWords.some(h => Math.abs(h.length - w.length) <= 1 && lev(h, w) <= 1));
      if (words.every(hit)) best = 35;
    }
    return Math.max(best, 0);
  }
  function scoreText(item, t, q) {
    if (t === q || (item.a && item.a.toLowerCase() === q)) return 100;
    if (t.startsWith(q)) return 80;
    if (t.split(/[\s,()-]+/).some(w => w.startsWith(q))) return 60;
    if (t.includes(q)) return 40;
    // tolerate one typo for longer queries
    if (q.length > 3) {
      const tol = q.length > 7 ? 2 : 1;
      for (const w of t.split(/\s+/)) if (Math.abs(w.length - q.length) <= tol && lev(w, q) <= tol) return 30;
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
  // "#rankings gdp" filters to one type; the tag matches the type name or its plural
  const TYPE_TAGS = { country: "Country", countries: "Country", ranking: "Ranking", rankings: "Ranking", indicator: "Indicator",
    indicators: "Indicator", compare: "Compare", comparisons: "Compare", geopolitics: "Geopolitics", tools: "Tool", tool: "Tool",
    reports: "Report", report: "Report", markets: "Market", market: "Market", cities: "City", city: "City" };
  function search(items, raw) {
    let q = norm(raw.trim());
    if (!q) return [];
    const tag = /^#(\w+)\s*(.*)$/.exec(q);
    if (tag && TYPE_TAGS[tag[1]]) {
      const k = TYPE_TAGS[tag[1]], pool = items.filter(it => it.k === k);
      if (!tag[2]) return pool.slice(0, 20);
      items = pool; q = tag[2];
    }
    const out = [];
    // "gdp india": a ranking plus a country opens that ranking with the country highlighted
    const words = q.split(/\s+/);
    if (words.length >= 2 && !/\b(vs\.?|versus)\b/.test(q)) {
      for (const cut of [1, words.length - 1]) {
        const [a, b] = [words.slice(0, cut).join(" "), words.slice(cut).join(" ")];
        for (const [cq, rq] of [[b, a], [a, b]]) {
          const c = bestCountry(items, cq);
          if (!c) continue;
          let best = null, bs = 0;
          for (const it of items) if (it.k === "Ranking") { const s = score(it, rq); if (s > bs) { bs = s; best = it; } }
          if (best && bs >= 40) { out.push({ t: `${best.t}: where ${c.t} ranks`, u: `${best.u}?hl=${c.a}`, k: "Ranking", f: c.f, s: c.t }); break; }
        }
        if (out.length) break;
      }
    }
    // "india vs" (or "india vs ch"): that country's comparison pages first
    const half = /^(.+?)\s+(?:vs\.?|versus|v)(?:\s+(.*))?$/.exec(q);
    if (half && !half[2]?.includes(",")) {
      const c = bestCountry(items, half[1]);
      const rest = half[2] ? norm(half[2]) : "";
      if (c) {
        const pairs = items.filter(it => it.k === "Compare" && norm(it.t).includes(norm(c.t))
          && (!rest || norm(it.t).replace(norm(c.t), "").includes(rest)));
        if (pairs.length) return pairs.slice(0, 10);
      }
    }
    const vs = q.split(/\s+(?:vs\.?|versus|v)\s+|\s*,\s*/).filter(Boolean);
    if (vs.length >= 2) {
      const cs = vs.map(v => bestCountry(items, v)).filter(Boolean);
      if (cs.length >= 2) {
        const page = cs.length === 2 && items.find(it => it.k === "Compare" && norm(it.t).includes(norm(cs[0].t)) && norm(it.t).includes(norm(cs[1].t)));
        out.push(page || { t: cs.map(c => c.t).join(" vs "), u: "/compare/#c=" + cs.map(c => c.a).join(","), k: "Compare" });
      }
    }
    return out.concat(items.map(it => [score(it, q), it]).filter(x => x[0] > 0)
      .sort((a, b) => b[0] - a[0] || a[1].t.length - b[1].t.length).slice(0, 12).map(x => x[1]));
  }
  function wire(input) {
    const box = input.parentElement.querySelector(".search-results");
    const bid = box.id || (box.id = "sr-" + Math.random().toString(36).slice(2, 8));
    input.setAttribute("role", "combobox"); input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-controls", bid); input.setAttribute("aria-expanded", "false");
    let sel = -1, hits = [];
    const palette = !!input.closest("#search-dialog");
    const opt = (h, i) => `<a href="${h.u}" role="option" id="${bid}-${i}"${i === sel ? ' class="sel" aria-selected="true"' : ' aria-selected="false"'}><span>${h.f ? window.atlasFlag(h.f) : `<i class="ty ty-${esc((h.k || "").toLowerCase())}" aria-hidden="true"></i>`}${esc(h.t)}</span><span class="k">${esc(h.k)}${h.s ? " · " + esc(h.s) : ""}</span></a>`;
    const draw = () => {
      if (palette && !input.value.trim()) hits = recent();
      if (palette && hits.length) {
        // grouped by type, in the order the types first appear
        const groups = [], at = {};
        hits.forEach((h, i) => { const k = !input.value.trim() ? "Recent" : h.k; if (!(k in at)) { at[k] = groups.length; groups.push([k, []]); } groups[at[k]][1].push([h, i]); });
        box.innerHTML = groups.map(([k, list]) => `<div role="group" aria-label="${esc(k)}"><p class="sr-group" aria-hidden="true">${esc(k)}</p>${list.map(([h, i]) => opt(h, i)).join("")}</div>`).join("");
      } else {
        box.innerHTML = hits.map(opt).join("") || (input.value.trim() ? '<a aria-disabled="true"><span class="muted">No matches. Try “india vs china”, “gdp india” or “#rankings”.</span></a>' : "");
      }
      const open = !!input.value.trim() || (palette && hits.length > 0);
      box.classList.toggle("open", open);
      input.setAttribute("aria-expanded", open);
      if (sel >= 0) input.setAttribute("aria-activedescendant", `${bid}-${sel}`); else input.removeAttribute("aria-activedescendant");
    };
    input.addEventListener("focus", () => { loadIndex(); if (palette && !input.value.trim()) { sel = -1; draw(); } });
    input.addEventListener("input", async () => { hits = search(await loadIndex(), input.value); sel = -1; draw(); });
    box.addEventListener("click", e => { const a = e.target.closest("a[href]"); if (a) remember(hits.find(h => h.u === a.getAttribute("href"))); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { sel = Math.min(sel + 1, hits.length - 1); draw(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
      else if (e.key === "Enter") { const h = hits[sel] || hits[0]; if (h) { remember(h); location.href = h.u; } }
      else if (e.key === "Escape") { if (box.classList.contains("open")) { box.classList.remove("open"); input.setAttribute("aria-expanded", "false"); } else { input.value = ""; } }
    });
    document.addEventListener("click", e => { if (!input.parentElement.contains(e.target)) box.classList.remove("open"); });
  }
  // recent destinations, in this browser only (storage can be unavailable: then there are simply none)
  function recent() { try { return JSON.parse(localStorage.getItem("recent-search") || "[]"); } catch (e) { return []; } }
  function remember(h) {
    if (!h) return;
    try { const r = [h, ...recent().filter(x => x.u !== h.u)].slice(0, 6); localStorage.setItem("recent-search", JSON.stringify(r.map(({ t, u, k, f, s }) => ({ t, u, k, f, s })))); } catch (e) {}
  }
  $$("[data-search]").forEach(wire);
  const dlg = $("#search-dialog");
  const openSearch = () => { dlg.showModal(); $("input", dlg).focus(); };
  $("#search-open")?.addEventListener("click", openSearch);
  { const q = new URLSearchParams(location.search).get("q");
    if (q && dlg) { openSearch(); const i = $("input", dlg); i.value = q; i.dispatchEvent(new Event("input", { bubbles: true })); } }
  document.addEventListener("keydown", e => {
    if ((e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !document.activeElement.isContentEditable)
        || (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey))) { e.preventDefault(); if (dlg && !dlg.open) openSearch(); }
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
  { const hl = new URLSearchParams(location.search).get("hl"), t = $("#ranking-table");
    if (hl && t) {
      const byLink = $$("tbody tr", t).find(r => r.dataset.iso === hl);
      if (byLink) { byLink.hidden = false; byLink.removeAttribute("data-unranked"); byLink.classList.add("hl-row"); setTimeout(() => byLink.scrollIntoView({ block: "center" }), 50); byLink.setAttribute("aria-current", "true"); }
    } }

  // ---------- ranking filters ----------
  $$("[data-filters]").forEach(bar => {
    const table = document.getElementById(bar.dataset.filters);
    const text = $("[data-f-text]", bar), region = $("[data-f-region]", bar), income = $("[data-f-income]", bar),
      ranked = $("[data-f-ranked]", bar), count = $("[data-f-count]", bar), trustOnly = $("[data-f-trust]", bar);
    const CAP = 50;
    let all = false, more = null;
    const apply = () => {
      const q = (text.value || "").toLowerCase(); let n = 0, total = 0;
      const capped = !all && !q && !region.value && !income.value && !trustOnly?.checked;
      for (const r of table.tBodies[0].rows) {
        const show = (!q || r.dataset.name.includes(q)) && (!region.value || r.dataset.region === region.value)
          && (!income.value || r.dataset.income === income.value) && (!ranked.checked || !("unranked" in r.dataset))
          && (!trustOnly?.checked || r.dataset.trust === "high");
        if (show) total++;
        r.hidden = !show || (capped && n >= CAP); if (!r.hidden) n++;
      }
      count.textContent = `${n} shown`;
      if (capped && total > CAP) {
        if (!more) {
          more = document.createElement("button");
          more.type = "button"; more.className = "btn ghost sm show-all";
          more.addEventListener("click", () => { all = true; apply(); table.tBodies[0].rows[CAP]?.querySelector("a")?.focus(); });
          table.closest(".table-wrap").after(more);
        }
        more.textContent = `Show all ${total} countries`; more.hidden = false;
      } else if (more) more.hidden = true;
    };
    [text, region, income, ranked, trustOnly].forEach(el => el?.addEventListener("input", apply));
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
  const fmtNum = v => NF.label(v);
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
    const [lib, geo] = await Promise.all([loadLib(), loadGeo()]);
    const go = async iso => { const idx = await loadIndex(); const hit = idx.find(i => i.a === iso); if (hit) location.href = hit.u; };
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
    // a container hidden or collapsed at load time has no size: wait until it has one
    if (!el.clientWidth || !el.clientHeight) {
      await new Promise(res => { const ro = new ResizeObserver(() => { if (el.clientWidth && el.clientHeight) { ro.disconnect(); res(); } }); ro.observe(el); });
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
    const slow = setTimeout(() => { if (!map.loaded()) mapNote(el, "The interactive map is taking a while; showing a static map for now."); }, 15000);
    map.on("load", () => { clearTimeout(slow); $(".map-static", el)?.remove(); mapNote(el, ""); });
    map.on("error", e => console.error("map", e && e.error));
    map.on("mousemove", "fill", e => {
      const p = e.features[0].properties; const v = el._values[p.iso3];
      tip.style.display = "block";
      tip.style.left = Math.min(e.point.x + 14, el.clientWidth - 180) + "px"; tip.style.top = (e.point.y + 14) + "px";
      tip.innerHTML = `<b>${esc(p.name)}</b><br>${v === undefined || v === null ? '<span class="muted">No data</span>' : esc(el._label) + ": " + fmtNum(v)}`;
      map.getCanvas().style.cursor = p.known ? "pointer" : "";
    });
    map.on("mouseleave", "fill", () => { tip.style.display = "none"; map.getCanvas().style.cursor = ""; });
    map.on("click", "fill", e => { const p = e.features[0].properties; if (p.known) go(p.iso3); });
  }
  function mapNote(el, text) {
    const n = $(".map-note", el.closest(".map-box"));
    if (n) { n.textContent = text; n.hidden = !text; }
  }
  const mapFailed = (el, err) => {
    console.error(err);
    mapNote(el, "The interactive map could not load, so a static version is shown (no zoom or hover).");
  };
  window.atlasMap = renderMap;
  const lite = !matchMedia("(pointer: fine)").matches || innerWidth < 768 || (navigator.connection && navigator.connection.saveData);
  if (lite) $$("[data-map]").forEach(el => {
    if (el.id === "explore-map") return;
    el._loading = true;                                   // skip automatic loading
    const b = document.createElement("button");
    b.type = "button"; b.className = "btn sm map-go"; b.textContent = "Explore the interactive map";
    b.addEventListener("click", () => { b.remove(); renderMap(el, JSON.parse($("[data-map-values]", el.closest(".map-box")).textContent)).catch(err => mapFailed(el, err)); });
    el.closest(".map-box").appendChild(b);
  });
  const io = "IntersectionObserver" in window ? new IntersectionObserver(entries => entries.forEach(en => {
    if (!en.isIntersecting || en.target._loading) return; io.unobserve(en.target); en.target._loading = true;
    const json = $("[data-map-values]", en.target.closest(".map-box"));
    renderMap(en.target, JSON.parse(json.textContent)).catch(err => mapFailed(en.target, err));
  }), { rootMargin: "200px" }) : null;
  $$("[data-map]").forEach(el => { if (el.id !== "explore-map") io?.observe(el); });
  // Fallback for browsers or embedded views where the observer never fires: load a map once it is on screen.
  const pending = () => $$("[data-map]").filter(el => el.id !== "explore-map" && !el._map && !el._loading);
  const check = () => pending().forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.top < innerHeight + 200 && r.bottom > -200) {
      el._loading = true; io?.unobserve(el);
      renderMap(el, JSON.parse($("[data-map-values]", el.closest(".map-box")).textContent)).catch(err => mapFailed(el, err));
    }
  });
  addEventListener("scroll", check, { passive: true }); setTimeout(check, 1500);

  document.addEventListener("themechange", () => $$("[data-map]").forEach(el => { if (el._map) renderMap(el, el._values, { lowerBetter: el._lowerBetter, label: el._label }); }));

  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  window.atlasEsc = esc;
})();
