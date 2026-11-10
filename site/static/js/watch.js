/* Watchlist: countries starred by the visitor, kept in localStorage only. Star buttons
   ([data-watch="ISO3"]) appear on country pages; /geopolitics/watchlist/ renders the list. */
(() => {
  const KEY = "atg-watch";
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (e) { return []; } };
  const write = l => { try { localStorage.setItem(KEY, JSON.stringify(l)); } catch (e) {} };

  document.querySelectorAll("[data-watch]").forEach(b => {
    const iso = b.dataset.watch;
    const paint = () => { const on = read().includes(iso); b.textContent = on ? "★ Watching" : "☆ Watch"; b.setAttribute("aria-pressed", on); };
    b.addEventListener("click", () => { const l = read(); write(l.includes(iso) ? l.filter(x => x !== iso) : [...l, iso]); paint(); });
    paint();
  });

  const out = document.getElementById("wl-out");
  if (!out) return;
  const form = document.getElementById("wl-form");
  form.addEventListener("submit", e => { e.preventDefault(); const l = read(); const c = form.c.value; if (!l.includes(c)) write([...l, c]); render(); });

  function spark(h) {
    if (!h || h.length < 2) return "";
    const W = 120, H = 30, ys = h.map(p => p[1]), lo = Math.min(...ys), hi = Math.max(...ys), x0 = h[0][0], x1 = h[h.length - 1][0];
    const pts = h.map(([x, y]) => `${(2 + (x - x0) / ((x1 - x0) || 1) * (W - 4)).toFixed(1)},${(H - 2 - (y - lo) / ((hi - lo) || 1) * (H - 4)).toFixed(1)}`).join(" ");
    return `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true"><polyline points="${pts}" fill="none" stroke="var(--bad)" stroke-width="1.6"/></svg>`;
  }
  const lastOf = s => s && s.length ? s[s.length - 1] : null;

  async function render() {
    const list = read();
    const feeds = document.getElementById("wl-feeds");
    if (!list.length) {
      out.innerHTML = `<p class="muted">Your watchlist is empty. Add a country above, or press “☆ Watch” on any country page.</p>`;
      if (feeds) feeds.innerHTML = "";
      return;
    }
    out.innerHTML = `<p class="muted">Loading…</p>`;
    const data = await Promise.all(list.map(id => fetch(`/geopolitics/data/${id}.json`).then(r => r.ok ? r.json() : null).catch(() => null)));
    const ok = data.filter(Boolean);
    out.innerHTML = `<div class="grid g3 wl-grid">${ok.map(d => {
      const us = lastOf(d.agree.USA), cn = lastOf(d.agree.CHN), ru = lastOf(d.agree.RUS);
      const h = d.risk_hist || [], ch = h.length > 5 ? (h[h.length - 1][1] - h[h.length - 6][1]) : null;
      return `<div class="card wl-card">
        <div class="wl-top"><h3><a href="/countries/${d.slug}/">${esc(d.name)}</a></h3><button type="button" class="linklike" data-rm="${d.id}">Remove</button></div>
        ${d.risk != null ? `<div class="wl-risk"><span class="rp-big" style="font-size:2rem">${Math.round(d.risk)}</span><span class="small muted">risk index · ${esc(d.risk_band)}${d.risk_rank ? ` · #${d.risk_rank[0]} of ${d.risk_rank[1]}` : ""}${ch != null ? ` · ${ch >= 0 ? "+" : ""}${ch.toFixed(0)} in 5 years` : ""}</span>${spark(h)}</div>` : ""}
        <ol class="mk-list">
          ${d.cand ? `<li><span>Conflict deaths in ${d.cand[0]} so far</span><span class="mono">${d.cand[1].toLocaleString("en")}</span></li>` : ""}
          ${us ? `<li><span>UN votes with the US (${us[0]})</span><span class="mono">${Math.round(100 * us[1])}%</span></li>` : ""}
          ${cn ? `<li><span>with China</span><span class="mono">${Math.round(100 * cn[1])}%</span></li>` : ""}
          ${ru ? `<li><span>with Russia</span><span class="mono">${Math.round(100 * ru[1])}%</span></li>` : ""}
        </ol>
        ${d.blocs && d.blocs.length ? `<p class="small muted" style="margin:8px 0 0">${d.blocs.map(esc).join(" · ")}</p>` : ""}
      </div>`; }).join("")}</div>
      <div class="section-head"><h2>Live news about your countries</h2></div>
      <div class="gd-news" data-gdelt data-query="${(n => n.length > 1 ? "(" + n.join(" OR ") + ")" : n[0])(ok.slice(0, 5).map(d => `&quot;${esc(d.name)}&quot;`))}" data-max="25" data-tabs="0" data-search="0"><p class="small muted gd-status">Loading live headlines…</p></div>`;
    out.querySelectorAll("[data-rm]").forEach(b => b.onclick = () => { write(read().filter(x => x !== b.dataset.rm)); render(); });
    out.querySelectorAll("[data-gdelt]").forEach(el => window.gdeltInit && window.gdeltInit(el));
    if (feeds) feeds.innerHTML = `<div class="card"><h3>Feeds for your countries</h3><ul class="small">${ok.map(d => `<li><a href="/feeds/countries/${d.slug}.xml">${esc(d.name)}</a></li>`).join("")}</ul></div>`;
  }
  render();
})();
