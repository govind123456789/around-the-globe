/* Why this rank: opens a short explanation under a ranking row, from the page's #why-data JSON. */
(() => {
  const data = document.getElementById("why-data");
  if (!data) return;
  const composite = data.dataset.kind === "original_composite";
  let why = null;
  const load = () => why ? Promise.resolve(why) : fetch(data.dataset.src).then(r => r.json()).then(d => (why = d));
  document.querySelectorAll(".why-btn").forEach(b => { b.type = "button"; b.setAttribute("aria-expanded", "false"); b.setAttribute("aria-controls", "why-" + b.dataset.why); });
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function body(w) {
    if (composite) {
      const peak = Math.max(...w.d.map(d => Math.abs(d[1])), 1);
      return `<p class="small">${esc(w.s)}</p><ol class="drivers">${w.d.map(([n, p]) =>
        `<li class="${p >= 0 ? "up" : "down"}"><span class="nm">${esc(n)}</span><span class="dbar" aria-hidden="true"><i style="width:${(50 * Math.abs(p) / peak).toFixed(1)}%"></i></span><span class="pts">${p >= 0 ? "+" : ""}${p.toFixed(1)}</span></li>`).join("")}</ol>
        <p class="small muted">Points against the median ranked country, at this index's weights.</p>`;
    }
    const near = [w.above && `${esc(w.above[1])} behind ${esc(w.above[0])} (one place up)`, w.below && `${esc(w.below[1])} ahead of ${esc(w.below[0])} (one place down)`].filter(Boolean).join("; ");
    const h = w.h || [];
    let spark = "";
    if (h.length > 1) {
      const W = 160, H = 34, xs = i => 4 + i * (W - 8) / (h.length - 1), maxR = Math.max(...h.map(x => x[1])), minR = Math.min(...h.map(x => x[1]));
      const ys = r => maxR === minR ? H / 2 : 4 + (r - minR) * (H - 8) / (maxR - minR);
      spark = `<svg class="spark" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Rank by year: ${h.map(x => x[0] + " " + x[1]).join(", ")}"><polyline fill="none" stroke="currentColor" stroke-width="1.6" points="${h.map((x, i) => xs(i).toFixed(1) + "," + ys(x[1]).toFixed(1)).join(" ")}"/></svg>`;
    }
    return `<p class="small">Value ${esc(w.v)}${w.y ? " (" + w.y + ")" : ""}.${near ? " " + near + "." : ""}</p>
      ${h.length ? `<p class="small muted">Rank among the countries with data for each year: ${h.map(x => `${x[0]}: ${x[1]} of ${x[2]}`).join(" · ")}</p>${spark}` : ""}`;
  }
  document.addEventListener("click", async e => {
    const b = e.target.closest(".why-btn");
    if (!b) return;
    try { await load(); } catch (err) { return; }
    const open = b.getAttribute("aria-expanded") === "true", cell = b.closest("td");
    document.querySelectorAll('.why-btn[aria-expanded="true"]').forEach(x => { if (x !== b) { x.setAttribute("aria-expanded", "false"); x.closest("td").querySelector(".why-box")?.remove(); } });
    if (open) { b.setAttribute("aria-expanded", "false"); cell.querySelector(".why-box")?.remove(); return; }
    const box = document.createElement("div");
    box.className = "why-box"; box.id = b.getAttribute("aria-controls");
    const w = why[b.dataset.why];
    box.innerHTML = body(w) + (w.m ? `<p class="small"><b>${esc(w.m)}</b></p>` : "");
    cell.appendChild(box); b.setAttribute("aria-expanded", "true");
  });
  document.addEventListener("keydown", e => {
    if (e.key !== "Escape") return;
    const b = document.querySelector('.why-btn[aria-expanded="true"]');
    if (b) { b.click(); b.focus(); }
  });
})();
