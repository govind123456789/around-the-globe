/* Relations explorer: two countries' UN vote agreement, conflict between their governments,
   refugee flows and risk, from /geopolitics/data/<ISO3>.json, plus live news about both. */
(() => {
  const form = document.getElementById("rel-form"), out = document.getElementById("rel-out");
  if (!form) return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const num = v => Math.round(v).toLocaleString("en-US");

  function chart(pts) {
    if (!pts || pts.length < 2) return `<p class="small muted">Not enough shared votes.</p>`;
    const W = 640, H = 240, L = 40, B = 26, T = 10, R = 12;
    const xs = pts.map(p => p[0]), x0 = Math.min(...xs), x1 = Math.max(...xs);
    const X = x => L + (x - x0) / ((x1 - x0) || 1) * (W - L - R), Y = v => T + (1 - v) * (H - T - B);
    const grid = [0, .25, .5, .75, 1].map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="grid"/><text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" class="tick">${v * 100}%</text>`).join("");
    const years = [x0, Math.round((x0 + x1) / 2), x1].map(y => `<text x="${X(y)}" y="${H - 6}" text-anchor="middle" class="tick">${y}</text>`).join("");
    const line = pts.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ");
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="UN vote agreement over time">${grid}${years}<polyline points="${line}" class="line s1" fill="none"/></svg>`;
  }

  async function run() {
    const fd = new FormData(form), a = fd.get("a"), b = fd.get("b");
    const opt = id => form.querySelector(`option[value="${id}"]`);
    const na = opt(a).dataset.name, nb = opt(b).dataset.name;
    if (a === b) { out.innerHTML = `<p class="muted">Pick two different countries.</p>`; return; }
    history.replaceState(null, "", `?a=${a}&b=${b}`);
    out.innerHTML = `<p class="muted">Loading…</p>`;
    const [A, Bd] = await Promise.all([a, b].map(id => fetch(`/geopolitics/data/${id}.json`).then(r => r.json())));
    const agree = A.agree[b] || [], last = agree[agree.length - 1], first = agree[0];
    const war = A.war[b] || [], warDeaths = war.reduce((s, x) => s + x[1], 0);
    const ab = (A.out.find(x => x[0] === b) || [, 0])[1], ba = (Bd.out.find(x => x[0] === a) || [, 0])[1];
    // where this pair sits among a's partners in the latest year
    let rank = null;
    if (last) {
      const vals = Object.values(A.agree).map(s => (s.find(x => x[0] === last[0]) || [])[1]).filter(v => v != null).sort((x, y) => y - x);
      rank = [vals.indexOf(last[1]) + 1, vals.length];
    }
    out.innerHTML = `
      <div class="section-head"><h2>${esc(na)} and ${esc(nb)}</h2><a href="/compare/">Compare their statistics →</a></div>
      <div class="stats mk-kpis">
        <div class="card stat"><span class="l">UN votes in agreement${last ? ", " + last[0] : ""}</span><span class="v">${last ? Math.round(100 * last[1]) + "%" : "—"}</span><span class="small muted">${first && last && first !== last ? Math.round(100 * first[1]) + "% in " + first[0] : ""}</span></div>
        <div class="card stat"><span class="l">Among ${esc(na)}’s partners</span><span class="v">${rank ? "#" + rank[0] : "—"}</span><span class="small muted">${rank ? "of " + rank[1] + " by agreement" : ""}</span></div>
        <div class="card stat"><span class="l">Deaths in fighting between their governments</span><span class="v">${num(warDeaths)}</span><span class="small muted">since 1989 · UCDP</span></div>
        <div class="card stat"><span class="l">Refugees and asylum seekers</span><span class="v">${num(ab + ba)}</span><span class="small muted">${esc(na)} → ${esc(nb)} ${num(ab)} · reverse ${num(ba)}</span></div>
      </div>
      <div class="grid g2">
        <div class="card"><h3>UN General Assembly agreement since 2000</h3>${chart(agree)}</div>
        <div class="card"><h3>Risk index</h3><ol class="mk-list"><li><span>${esc(na)}</span><span class="mono">${A.risk ?? "—"}</span></li><li><span>${esc(nb)}</span><span class="mono">${Bd.risk ?? "—"}</span></li></ol>
          ${war.length ? `<h3 style="margin-top:16px">Years of armed conflict between the governments</h3><ol class="mk-list">${war.slice(-8).reverse().map(x => `<li><span>${x[0]}</span><span class="mono">${num(x[1])} deaths</span></li>`).join("")}</ol>` : `<p class="small muted">No recorded fighting between the two governments since 1989.</p>`}
          <p class="small"><a href="/geopolitics/risk/">How the risk index works →</a></p></div>
      </div>
      <div class="section-head"><h2>Live news about both</h2></div>
      <div class="gd-news compact" data-gdelt data-query="&quot;${esc(na)}&quot; &quot;${esc(nb)}&quot;" data-max="15" data-tabs="0" data-search="0"><p class="small muted gd-status">Loading live headlines…</p></div>`;
    out.querySelectorAll("[data-gdelt]").forEach(el => window.gdeltInit && window.gdeltInit(el));
  }

  form.addEventListener("submit", e => { e.preventDefault(); run().catch(err => { out.innerHTML = `<p class="muted">Could not load the data (${esc(err.message)}).</p>`; }); });
  const q = new URLSearchParams(location.search);
  if (q.get("a") && q.get("b")) { form.a.value = q.get("a"); form.b.value = q.get("b"); }
  run().catch(() => {});
})();
