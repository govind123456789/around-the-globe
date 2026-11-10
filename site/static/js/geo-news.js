/* Live geopolitical headlines from the GDELT DOC 2.0 API, fetched in the visitor's browser.
   GDELT asks for at most one request every five seconds, so requests go through a queue and
   results are cached for 15 minutes in sessionStorage. Headlines link to the original publisher. */
(() => {
  const API = "https://api.gdeltproject.org/api/v2/doc/doc";
  const GAP = 5600, TTL = 15 * 60 * 1000;
  const THEMES = {
    all: ["Top stories", "(war OR sanctions OR diplomacy OR ceasefire OR military)"],
    conflict: ["War & conflict", "(war OR airstrike OR ceasefire OR offensive OR militants)"],
    diplomacy: ["Diplomacy", '(diplomacy OR summit OR treaty OR "foreign minister" OR "peace talks")'],
    sanctions: ["Sanctions & trade", '(sanctions OR tariffs OR embargo OR "export controls" OR "trade war")'],
    elections: ["Elections & unrest", "(election OR referendum OR coup OR protests OR unrest)"],
  };
  // Default to established international outlets; the news page can widen this to all world media.
  const TRUSTED = "(domain:reuters.com OR domain:apnews.com OR domain:bbc.co.uk OR domain:aljazeera.com OR domain:theguardian.com)";
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let last = 0, chain = Promise.resolve();

  function cached(url) {
    try { const c = JSON.parse(sessionStorage.getItem("gd:" + url) || "null"); if (c && Date.now() - c.t < TTL) return c.d; } catch (e) {}
    return null;
  }
  function store(url, d) { try { sessionStorage.setItem("gd:" + url, JSON.stringify({ t: Date.now(), d })); } catch (e) {} }

  function get(url) {
    const c = cached(url);
    if (c) return Promise.resolve(c);
    const job = chain.then(async () => {
      // GDELT answers over-limit requests without CORS headers, so the browser reports a network
      // error: wait and retry a few times before giving up.
      for (let attempt = 0; attempt < 4; attempt++) {
        const wait = Math.max(0, last + GAP * (attempt + 1) - Date.now());
        if (wait) await new Promise(r => setTimeout(r, wait));
        last = Date.now();
        try {
          const r = await fetch(url);
          const text = await r.text();
          if (r.ok && text.trim()[0] === "{") { const d = JSON.parse(text); store(url, d); return d; }
          if (r.ok && /too short or too long/i.test(text)) throw new Error("toolong");
          if (r.status !== 429 && r.ok) throw new Error("unavailable");
        } catch (e) { if (e.message === "unavailable" || e.message === "toolong") throw e; }
      }
      throw new Error("busy");
    });
    chain = job.catch(() => {});
    return job;
  }

  function ago(s) {
    const m = /^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)/.exec(s || "");
    if (!m) return "";
    const t = Date.UTC(+m[1], m[2] - 1, +m[3], +m[4], +m[5]), mins = Math.round((Date.now() - t) / 60000);
    if (mins < 60) return `${Math.max(1, mins)} min ago`;
    if (mins < 48 * 60) return `${Math.round(mins / 60)} h ago`;
    return `${Math.round(mins / 1440)} days ago`;
  }

  function query(el, theme) {
    const page = document;
    const base = el.dataset.query || "";
    const parts = [];
    if (base) parts.push(base);
    if (el.dataset.tabs === "1" || !base) parts.push(THEMES[theme || "all"][1]);
    if (el.dataset.search === "1") {
      const c = page.querySelector("[data-gd-country]")?.value, q = page.querySelector("[data-gd-q]")?.value.trim();
      if (c) parts.push(`"${c.replace(/"/g, "")}"`);
      if (q) parts.push(/\s/.test(q) && !/["()]/.test(q) ? `"${q}"` : q);
    }
    const en = el.dataset.search === "1" ? page.querySelector("[data-gd-en]")?.checked !== false : true;
    const trusted = el.dataset.search === "1" ? page.querySelector("[data-gd-trusted]")?.checked !== false : true;
    if (trusted) parts.push(TRUSTED);
    else if (en) parts.push("sourcelang:english");
    const max = Math.min(75, +el.dataset.max || 20);
    return `${API}?query=${encodeURIComponent(parts.join(" "))}&mode=artlist&maxrecords=${max}&format=json&sort=hybridrel&timespan=3d`;
  }

  function render(el, d) {
    const seen = new Set();
    const items = (d.articles || []).filter(a => { const k = (a.title || "").toLowerCase().slice(0, 80); if (!k || seen.has(k)) return false; seen.add(k); return true; });
    const box = el.querySelector(".gd-list") || el.appendChild(Object.assign(document.createElement("div"), { className: "gd-list" }));
    if (!items.length) { box.innerHTML = `<p class="small muted">No matching headlines in the last three days.</p>`; return; }
    box.innerHTML = `<ol class="gd-items">${items.map(a => `<li class="gd-item">
        ${a.socialimage && !el.classList.contains("compact") ? `<img class="gd-img" src="${esc(a.socialimage)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : ""}
        <div><a class="gd-title" href="${esc(a.url)}" target="_blank" rel="noopener nofollow ugc">${esc(a.title)}</a>
        <div class="gd-meta">${esc(a.domain)}${a.sourcecountry ? " · " + esc(a.sourcecountry) : ""}${a.language && a.language !== "English" ? " · " + esc(a.language) : ""} · ${ago(a.seendate)}</div></div></li>`).join("")}</ol>`;
  }

  function load(el, theme) {
    const status = el.querySelector(".gd-status");
    if (status) { status.textContent = "Loading live headlines…"; status.hidden = false; }
    const url = query(el, theme);
    const show = d => { if (status) status.hidden = true; render(el, d); };
    return get(url).then(show).catch(err => {
      // a query GDELT finds too long falls back to all English-language media
      if (err.message === "toolong" && url.includes("domain%3A")) {
        return get(url.replace(encodeURIComponent(" " + TRUSTED), encodeURIComponent(" sourcelang:english"))).then(show);
      }
      throw err;
    }).catch(err => {
      if (status) {
        status.hidden = false;
        status.innerHTML = err.message === "busy" ? `The news service is busy (it allows one request every few seconds). <button type="button" class="linklike">Try again</button>` : `Live news is unavailable right now. <button type="button" class="linklike">Try again</button>`;
        status.querySelector("button").onclick = () => load(el, theme);
      }
    });
  }

  function init(el) {
    if (el._gd) return;
    el._gd = true;
    let theme = "all";
    if (el.dataset.tabs === "1") {
      const tabs = document.createElement("div");
      tabs.className = "gd-tabs";
      tabs.setAttribute("role", "tablist");
      tabs.innerHTML = Object.entries(THEMES).map(([k, [label]]) => `<button type="button" role="tab" data-k="${k}" aria-selected="${k === "all"}">${label}</button>`).join("");
      el.prepend(tabs);
      tabs.addEventListener("click", e => {
        const b = e.target.closest("button[data-k]");
        if (!b) return;
        theme = b.dataset.k;
        tabs.querySelectorAll("button").forEach(x => x.setAttribute("aria-selected", x === b));
        load(el, theme);
      });
    }
    if (el.dataset.search === "1") {
      let t;
      const again = () => { clearTimeout(t); t = setTimeout(() => load(el, theme), 500); };
      document.querySelector("[data-gd-country]")?.addEventListener("change", again);
      document.querySelector("[data-gd-en]")?.addEventListener("change", again);
      document.querySelector("[data-gd-trusted]")?.addEventListener("change", again);
      document.querySelector("[data-gd-q]")?.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); again(); } });
      const c = new URLSearchParams(location.search).get("c");
      const sel = document.querySelector("[data-gd-country]");
      if (c && sel) sel.value = [...sel.options].find(o => o.value.toLowerCase() === c.toLowerCase())?.value || "";
    }
    load(el, theme);
  }

  window.gdeltInit = init;
  const start = () => document.querySelectorAll("[data-gdelt]").forEach(init);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
