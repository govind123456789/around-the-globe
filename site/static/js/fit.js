/* Where would I fit? Weighted average of each country's rank (0-1) on the factors the visitor cares
   about. Data: /lab/fit/data.json {factors:[{key,label,ind}], countries:{ISO:{n,s,v:{key:rank}}}} */
(() => {
  const box = document.getElementById("fit-sliders"), out = document.getElementById("fit-out");
  if (!box) return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const DEFAULT = { income: 2, health: 2, safety: 3, peace: 2, air: 1, voice: 1 };
  let data;
  const weights = () => Object.fromEntries([...box.querySelectorAll("input[type=range]")].map(i => [i.name, +i.value]));

  function render() {
    const w = weights(), keys = Object.keys(w).filter(k => w[k] > 0);
    history.replaceState(null, "", "?" + keys.map(k => `${k}=${w[k]}`).join("&"));
    if (!keys.length) { out.innerHTML = `<p class="muted">Move at least one slider.</p>`; return; }
    const scored = Object.entries(data.countries).map(([iso, c]) => {
      let s = 0, tw = 0;
      for (const k of keys) { const v = c.v[k]; if (v != null) { s += v * w[k]; tw += w[k]; } }
      const cover = tw / keys.reduce((a, k) => a + w[k], 0);
      return { iso, c, score: tw ? s / tw : null, cover };
    }).filter(r => r.score != null && r.cover >= 0.7).sort((a, b) => b.score - a.score);
    const label = Object.fromEntries(data.factors.map(f => [f.key, f.label]));
    const top = scored.slice(0, 12);
    out.innerHTML = `<div class="card"><h3>Your best matches</h3><ol class="fit-list">${top.map((r, k) => {
      const best = keys.filter(x => r.c.v[x] != null).sort((a, b) => r.c.v[b] - r.c.v[a]);
      return `<li><span class="rk">${k + 1}</span><div><a href="/countries/${r.c.s}/"><b>${esc(r.c.n)}</b></a>
        <div class="small muted">Strongest: ${best.slice(0, 2).map(x => esc(label[x])).join(", ")}${best.length > 2 && r.c.v[best[best.length - 1]] < 0.5 ? ` · weaker on ${esc(label[best[best.length - 1]])}` : ""}</div></div>
        <span class="fit-score">${Math.round(100 * r.score)}<small>/100</small></span></li>`; }).join("")}</ol>
      <p class="small muted" style="margin:10px 0 0">Score = how high the country ranks, on average, on what you chose (100 = top on everything). ${scored.length} countries compared.</p></div>`;
  }

  fetch("/lab/fit/data.json").then(r => r.json()).then(d => {
    data = d;
    const q = new URLSearchParams(location.search), fromUrl = [...q.keys()].length > 0;
    box.innerHTML = d.factors.map(f => {
      const v = fromUrl ? (+q.get(f.key) || 0) : (DEFAULT[f.key] || 0);
      return `<label class="fit-row"><span>${esc(f.label)}</span><input type="range" name="${f.key}" min="0" max="3" step="1" value="${v}" aria-label="${esc(f.label)}"><b>${v}</b></label>`;
    }).join("");
    box.addEventListener("input", e => { if (e.target.type === "range") { e.target.nextElementSibling.textContent = e.target.value; render(); } });
    render();
  }).catch(() => { box.innerHTML = `<p class="muted">Could not load the data.</p>`; });
})();
