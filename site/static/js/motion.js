/* Motion: reveal content as it scrolls into view, count numbers up, grow bars and draw charts.
   Everything is skipped when the visitor asks for reduced motion, and content is never hidden
   unless this script is running (the html.anim class gates every hidden state). */
(() => {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const root = document.documentElement;
  root.classList.add("anim");

  const SEL = [
    "main .section-head", "main .card", "main .table-wrap", "main .map-box", "main .pos", "main .stat",
    "main .mk-bars", "main .mk-list", "main .rp-finding", "main .rp-section", "main .prose > h2", "main .chart-card"
  ].join(",");
  const NUM = /([+\-−]?\d[\d,]*\.?\d*)/;

  // ---- count-up: animate the first number in an element's text, keeping its format
  function countUp(el) {
    if (el._counted || el.closest("[data-live]") || el.hasAttribute("data-live")) return;
    el._counted = true;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) { if (NUM.test(node.nodeValue)) break; }
    if (!node) return;
    const text = node.nodeValue, m = text.match(NUM), raw = m[1];
    const target = parseFloat(raw.replace(/,/g, "").replace("−", "-"));
    if (!isFinite(target) || target === 0) return;
    const dec = (raw.split(".")[1] || "").length, comma = raw.includes(","), sign = /^[+]/.test(raw);
    const fmt = v => {
      let s = Math.abs(v).toFixed(dec);
      if (comma) { const [i, d] = s.split("."); s = i.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (d ? "." + d : ""); }
      return (v < 0 ? (raw.startsWith("−") ? "−" : "-") : sign ? "+" : "") + s;
    };
    const t0 = performance.now(), dur = 1100;
    const step = now => {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      node.nodeValue = text.replace(raw, fmt(target * e));
      if (p < 1) requestAnimationFrame(step); else node.nodeValue = text;
    };
    requestAnimationFrame(step);
  }

  // ---- draw line charts and sparklines
  function draw(el) {
    el.querySelectorAll("svg.chart polyline.line, svg.spark polyline, svg.chart path.line").forEach(p => {
      if (p._drawn) return;
      p._drawn = true;
      let len = 0;
      try { len = p.getTotalLength(); } catch (e) { return; }
      if (!len) return;
      p.style.strokeDasharray = len; p.style.strokeDashoffset = len;
      p.getBoundingClientRect();
      p.style.transition = "stroke-dashoffset 1.4s cubic-bezier(.2,.7,.2,1)";
      p.style.strokeDashoffset = 0;
    });
  }

  function show(el) {
    if (el._shown) return;
    el._shown = true;
    el.classList.add("in");
    setTimeout(() => el.style.setProperty("--d", "0ms"), 1600);
    el.querySelectorAll(".stat .v, .mk-big, .rk, .rp-big, .facts b, .num-up").forEach(countUp);
    if (el.matches(".stat .v, .mk-big, .num-up")) countUp(el);
    draw(el);
  }

  function setup() {
    const els = [...document.querySelectorAll(SEL)].filter(el => !el.closest(".nav, header, .band, .nav-panel") && !el.parentElement.closest(".rv"));
    const groups = new Map();
    els.forEach(el => {
      el.classList.add("rv");
      const k = el.parentElement, i = groups.get(k) || 0;
      groups.set(k, i + 1);
      el.style.setProperty("--d", Math.min(i, 8) * 70 + "ms");
    });
    const pending = new Set(els);
    const check = () => pending.forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.top < innerHeight - 40 && r.bottom > 0) { pending.delete(el); show(el); }
    });
    const io = "IntersectionObserver" in window && new IntersectionObserver(es => es.forEach(en => {
      if (en.isIntersecting) { pending.delete(en.target); io.unobserve(en.target); show(en.target); }
    }), { rootMargin: "0px 0px -40px 0px" });
    if (io) els.forEach(el => io.observe(el));
    addEventListener("scroll", check, { passive: true });
    addEventListener("resize", check);
    check();
    setTimeout(check, 400);
    // charts and numbers in the hero band are visible from the start
    document.querySelectorAll(".band").forEach(b => { draw(b); b.querySelectorAll(".facts b").forEach(countUp); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup); else setup();
})();
