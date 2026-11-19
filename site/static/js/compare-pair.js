/* Comparison page: section tabs, find, big differences, stale and trust filters. No reload; rows are
   filtered in place, so no indicator is ever shown twice. */
(() => {
  const table = document.getElementById("pair-table");
  if (!table) return;
  const tabs = document.querySelector(".cmp-tabs"), q = document.querySelector("[data-cmp-q]"),
    big = document.querySelector("[data-cmp-big]"), stale = document.querySelector("[data-cmp-stale]"),
    tr = document.querySelector("[data-cmp-trust]"), count = document.querySelector("[data-cmp-count]"),
    panel = document.getElementById("pair-panel"), wrap = table.closest(".table-wrap");
  let tab = "overview";
  wrap.classList.remove("hide-old");
  function apply() {
    const text = (q.value || "").trim().toLowerCase();
    let n = 0;
    for (const body of table.tBodies) {
      let shown = 0;
      const inTab = tab === "all" || tab === "overview" || body.dataset.dim === tab;
      for (const r of body.rows) {
        if (!r.classList.contains("ind-row")) continue;
        const ok = inTab && (tab !== "overview" || text || "head" in r.dataset)
          && (!text || r.dataset.name.includes(text))
          && (!big.checked || "big" in r.dataset)
          && (!stale.checked || !("stale" in r.dataset))
          && (!tr.checked || r.dataset.trust === "high");
        r.hidden = !ok;
        if (ok) { shown++; n++; }
      }
      body.hidden = !shown;
    }
    count.textContent = n === 1 ? "1 indicator shown" : `${n} indicators shown`;
  }
  tabs.hidden = false;
  const buttons = [...tabs.querySelectorAll('[role="tab"]')];
  function select(b, focus) {
    buttons.forEach(x => { const on = x === b; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1; });
    tab = b.dataset.tab;
    panel.setAttribute("aria-labelledby", b.id);
    if (focus) b.focus();
    apply();
  }
  tabs.addEventListener("click", e => { const b = e.target.closest('[role="tab"]'); if (b) select(b); });
  tabs.addEventListener("keydown", e => {
    const i = buttons.indexOf(document.activeElement);
    if (i < 0) return;
    const to = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : null;
    if (to === null) return;
    e.preventDefault();
    select(buttons[(to + buttons.length) % buttons.length], true);
  });
  [q, big, stale, tr].forEach(el => el.addEventListener("input", apply));
  [big, stale, tr].forEach(el => el.addEventListener("change", apply));
  apply();
  // draw the small trend lines (data-sp="x:y,...|x:y,..."), only once each
  const ns = "http://www.w3.org/2000/svg";
  for (const td of table.querySelectorAll("td[data-sp]")) {
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("class", "pspark"); svg.setAttribute("viewBox", "0 0 72 18"); svg.setAttribute("width", "72"); svg.setAttribute("height", "18");
    svg.setAttribute("aria-hidden", "true");
    td.dataset.sp.split("|").forEach((s, i) => {
      if (!s || s.indexOf(",") < 0) return;
      const pl = document.createElementNS(ns, "polyline");
      pl.setAttribute("class", "s" + (i + 1));
      pl.setAttribute("points", s.split(",").map(p => { const [x, y] = p.split(":"); return `${1 + x * 70 / 19},${17 - y}`; }).join(" "));
      svg.appendChild(pl);
    });
    td.appendChild(svg);
  }
})();
