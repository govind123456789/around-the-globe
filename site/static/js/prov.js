/* Source badges: a popover with the full provenance of a value, from the page's #prov-data table.
   A badge is a <button>; one popover at a time; Esc or a click elsewhere closes it and returns focus. */
(() => {
  const el = document.getElementById("prov-data");
  if (!el) return;
  const P = JSON.parse(el.textContent);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const LV = { h: ["High", "●●●"], m: ["Medium", "●●○"], l: ["Low", "●○○"] };
  const pop = document.createElement("div");
  pop.id = "prov-pop"; pop.className = "prov-pop"; pop.setAttribute("role", "dialog"); pop.setAttribute("aria-label", "Source details"); pop.hidden = true;
  document.body.appendChild(pop);
  let owner = null;
  // badges are plain buttons in the HTML; make them disclosure buttons, labelled with their trust level
  document.querySelectorAll(".sb").forEach(b => {
    b.type = "button"; b.setAttribute("aria-expanded", "false");
    const v = P.v[+b.dataset.p];
    if (v) b.setAttribute("aria-label", `${b.textContent.trim()}, ${LV[v[3]][0]} trust. Source details`);
  });

  function body(k, differ) {
    const [ind, year, st, lv, age] = P.v[k], [name, code, sid, retrieved, note] = P.i[ind];
    const [pub, url, lic, licUrl, kind, lag, short] = P.s[sid];
    const old = P.r - year;
    const ageText = age === "o" ? `${old} years old, well past this source's usual ${lag}-year lag`
      : age === "a" ? `${old} years old, older than this source usually is` : "recent for this source";
    const reasons = [`Data from ${year}: ${ageText}`, kind];
    if (st === "e") reasons.push("The source marks this value as an estimate");
    if (st === "f") reasons.push("A projection of a future year");
    return `<p class="pp-h"><b>${esc(pub)}</b>${code ? ` <span class="muted">· ${esc(code)}</span>` : ""}</p>
      <dl class="pp-dl">
        <dt>Series</dt><dd>${esc(name)}</dd>
        <dt>Data year</dt><dd>${year}${differ ? ` <span class="stale">· years differ between the values compared</span>` : ""}</dd>
        ${retrieved ? `<dt>Retrieved</dt><dd>${esc(retrieved)}</dd>` : ""}
        <dt>Licence</dt><dd>${licUrl ? `<a href="${esc(licUrl)}" rel="noopener">${esc(lic)}</a>` : esc(lic)}</dd>
        ${note ? `<dt>Method</dt><dd>${esc(note)}</dd>` : ""}
        <dt>Trust</dt><dd><span aria-hidden="true">${LV[lv][1]}</span> ${LV[lv][0]}: ${reasons.map(esc).join("; ")}.</dd>
      </dl>
      <p class="pp-links">${url ? `<a href="${esc(url)}" rel="noopener">Original source ↗</a> · ` : ""}<a href="/data/indicators/${esc(ind)}/">This indicator</a> · <a href="/methodology/trust/">Trust levels</a> · <a href="/methodology/">Methodology</a></p>`;
  }
  function close(focus) {
    if (!owner) return;
    owner.setAttribute("aria-expanded", "false"); owner.removeAttribute("aria-controls");
    pop.hidden = true;
    if (focus) owner.focus();
    owner = null;
  }
  function open(b) {
    close(false);
    owner = b;
    pop.innerHTML = body(+b.dataset.p, b.classList.contains("yd")) + '<button type="button" class="pp-x" aria-label="Close">×</button>';
    pop.hidden = false;
    b.setAttribute("aria-expanded", "true"); b.setAttribute("aria-controls", "prov-pop");
    const r = b.getBoundingClientRect(), w = Math.min(340, innerWidth - 24);
    if (innerWidth < 640) { pop.style.cssText = ""; pop.classList.add("sheet"); }
    else {
      pop.classList.remove("sheet");
      pop.style.left = Math.max(12, Math.min(r.left + scrollX, scrollX + innerWidth - w - 12)) + "px";
      pop.style.top = (r.bottom + scrollY + 6) + "px"; pop.style.width = w + "px";
    }
    pop.querySelector("a, .pp-x")?.focus({ preventScroll: true });
  }
  document.addEventListener("click", e => {
    const b = e.target.closest(".sb");
    if (b) { e.preventDefault(); owner === b ? close(true) : open(b); return; }
    if (e.target.closest(".pp-x")) { close(true); return; }
    if (owner && !pop.contains(e.target)) close(false);
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && owner) { e.preventDefault(); close(true); } });
  pop.addEventListener("focusout", e => { if (owner && !pop.contains(e.relatedTarget) && e.relatedTarget !== owner) close(false); });
})();
