/* Daily quiz: ten "which country has more?" questions, chosen with a seed from today's date so
   everyone gets the same set. Data: /quiz/data.json {inds:[{id,q,unit,d,src}], c:{ISO:{n,f}}, v:{ind:{ISO:[year,value]}}} */
(() => {
  const box = document.getElementById("quiz");
  if (!box) return;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const today = new Date().toISOString().slice(0, 10);
  let seed = [...today].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7);
  const rnd = () => { seed ^= seed << 13; seed >>>= 0; seed ^= seed >> 17; seed ^= seed << 5; seed >>>= 0; return seed / 4294967296; };
  const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} } };
  const fmt = (v, d, u) => {
    const a = Math.abs(v);
    let s = a >= 1e12 ? (v / 1e12).toFixed(1) + " tn" : a >= 1e9 ? (v / 1e9).toFixed(1) + " bn" : a >= 1e6 ? (v / 1e6).toFixed(1) + " m" : v.toLocaleString("en-US", { maximumFractionDigits: d });
    if (u.startsWith("current US$") || u.includes("international $")) s = "$" + s;
    return u.startsWith("%") ? s + "%" : s + (u && !u.startsWith("current") && !u.includes("$") ? " " + u : "");
  };

  function makeQuestions(data) {
    const qs = [], used = new Set();
    let guard = 0;
    while (qs.length < 10 && guard++ < 500) {
      const ind = data.inds[Math.floor(rnd() * data.inds.length)];
      const vals = Object.entries(data.v[ind.id] || {});
      if (vals.length < 10) continue;
      const [a, b] = [vals[Math.floor(rnd() * vals.length)], vals[Math.floor(rnd() * vals.length)]];
      if (a[0] === b[0] || a[1][1] === b[1][1]) continue;
      const ratio = Math.max(a[1][1], b[1][1]) / Math.max(1e-9, Math.min(a[1][1], b[1][1]));
      if (ratio < 1.08) continue;                       // too close to call fairly
      const key = [ind.id, a[0], b[0]].sort().join();
      if (used.has(key)) continue;
      used.add(key);
      qs.push({ ind, a, b });
    }
    return qs;
  }

  function run(data) {
    const qs = makeQuestions(data);
    const done = store.get("atg-quiz-" + today, null);
    let i = 0, score = 0;
    const answers = [];
    if (done) return finish(done.score, done.answers, qs, data, true);

    function ask() {
      const { ind, a, b } = qs[i];
      const flag = iso => data.c[iso].f ? `<img class="flag" src="/static/flags/${data.c[iso].f}.svg" alt="" width="20" height="15">` : "";
      box.innerHTML = `<div class="quiz-top"><span class="mk-kicker">Question ${i + 1} of ${qs.length}</span><span class="small muted">Score ${score}</span></div>
        <h2 class="quiz-q">${esc(ind.q)}</h2>
        <div class="quiz-opts">${[a, b].map(([iso]) => `<button type="button" class="quiz-opt" data-iso="${iso}">${flag(iso)}${esc(data.c[iso].n)}</button>`).join("")}</div>
        <div class="quiz-ans" hidden></div>`;
      box.querySelectorAll(".quiz-opt").forEach(btn => btn.addEventListener("click", () => {
        const pick = btn.dataset.iso, win = (ind.low ? a[1][1] < b[1][1] : a[1][1] > b[1][1]) ? a[0] : b[0], ok = pick === win;
        if (ok) score++;
        answers.push(ok ? 1 : 0);
        box.querySelectorAll(".quiz-opt").forEach(x => { x.disabled = true; x.classList.add(x.dataset.iso === win ? "right" : x.dataset.iso === pick ? "wrong" : "other"); });
        const ans = box.querySelector(".quiz-ans");
        ans.hidden = false;
        ans.innerHTML = `<p><b>${ok ? "Right." : "Not quite."}</b> ${[a, b].map(([iso, [y, v]]) => `${esc(data.c[iso].n)}: <b>${fmt(v, ind.d, ind.unit)}</b> (${y})`).join(" · ")}</p>
          <p class="small muted">${esc(ind.src)} · <a href="/data/indicators/${ind.id}/">about this indicator</a></p>
          <button type="button" class="btn sm">${i + 1 < qs.length ? "Next question →" : "See my score"}</button>`;
        ans.querySelector("button").addEventListener("click", () => { i++; i < qs.length ? ask() : finish(score, answers, qs, data, false); });
        ans.querySelector("button").focus();
      }));
    }
    ask();
  }

  function finish(score, answers, qs, data, already) {
    const prev = store.get("atg-quiz-last", null);
    if (!already) {
      store.set("atg-quiz-" + today, { score, answers });
      const y = new Date(Date.now() - 864e5).toISOString().slice(0, 10);
      const streak = prev && (prev.day === y || prev.day === today) ? (prev.day === today ? prev.streak : prev.streak + 1) : 1;
      store.set("atg-quiz-last", { day: today, streak });
    }
    const streak = (store.get("atg-quiz-last", { streak: 1 })).streak;
    const grid = answers.map(x => x ? "🟩" : "🟥").join("");
    const text = `Around the Globe daily quiz ${today}: ${score}/${qs.length}\n${grid}\n${location.origin}/quiz/`;
    box.innerHTML = `<span class="mk-kicker">${already ? "You've played today" : "Done"}</span>
      <div class="quiz-score">${score}<small>/${qs.length}</small></div>
      <p class="quiz-grid" aria-label="${score} right out of ${qs.length}">${grid}</p>
      <p class="small muted">Streak: ${streak} day${streak === 1 ? "" : "s"}. New questions tomorrow.</p>
      <div class="mk-actions"><button type="button" class="btn sm" id="quiz-share">Copy my result</button><a class="btn ghost sm" href="/rankings/">Explore the rankings</a></div>`;
    document.getElementById("quiz-share").addEventListener("click", e => { navigator.clipboard?.writeText(text); e.target.textContent = "Copied"; });
  }

  fetch("/quiz/data.json").then(r => r.json()).then(run).catch(() => { box.innerHTML = `<p class="muted">Could not load the quiz.</p>`; });
})();
