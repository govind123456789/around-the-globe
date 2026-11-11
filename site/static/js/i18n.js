/* Interface translation (menus, headings, buttons and labels) into Hindi, Spanish, French and Arabic.
   Data names, values and generated sentences stay in English. The choice is kept in localStorage;
   Arabic switches the page to right-to-left. Original English text is restored when switching back. */
(() => {
  const LANGS = { en: "English", hi: "हिन्दी", es: "Español", fr: "Français", ar: "العربية" };
  // English -> [Hindi, Spanish, French, Arabic]
  let T = window.ATG_T || null;

  const IDX = { hi: 0, es: 1, fr: 2, ar: 3 };
  const SEL = "header.top a, header.top summary, .utility a, .nav-panel a, .nav-panel h4, .nav-extra a, footer.site h4, footer.site a, " +
              ".section-head h2, .section-head a, .geo-nav a, .lab-nav a, .btn, button, label > span, legend, .gd-tabs button, .rp-summary h2, " +
              ".card h3, th, .mk-others a, .geo-src b";
  const KEY = "atg-lang";
  const get = () => { try { return localStorage.getItem(KEY) || "en"; } catch (e) { return "en"; } };

  function loadDict() {
    if (T) return Promise.resolve(T);
    return new Promise((res, rej) => {
      const sc = document.createElement("script");
      sc.src = (document.querySelector('script[src*="i18n.js"]')?.src || "/static/js/i18n.js").replace("i18n.js", "i18n-dict.js");
      sc.onload = () => { T = window.ATG_T; res(T); }; sc.onerror = rej;
      document.head.appendChild(sc);
    });
  }
  function apply(lang) {
    if (lang !== "en" && !T) { loadDict().then(() => apply(lang)); return; }
    const html = document.documentElement;
    html.lang = lang; html.dir = lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll(SEL).forEach(el => {
      el.childNodes.forEach(n => {
        if (n.nodeType !== 3) return;
        if (n._en === undefined) n._en = n.nodeValue;
        const raw = n._en, key = raw.trim();
        if (lang === "en" || !key) { n.nodeValue = raw; return; }
        const t = T && (T[key] || T[key.replace(/\s+/g, " ")]);
        n.nodeValue = t ? raw.replace(key, t[IDX[lang]]) : raw;
      });
    });
  }

  function mount() {
    const bar = document.querySelector(".utility .wrap");
    if (bar && !document.getElementById("lang-select")) {
      const sel = document.createElement("select");
      sel.id = "lang-select"; sel.className = "lang-select"; sel.setAttribute("aria-label", "Language");
      sel.innerHTML = Object.entries(LANGS).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
      sel.value = get();
      sel.addEventListener("change", () => { try { localStorage.setItem(KEY, sel.value); } catch (e) {} apply(sel.value); });
      bar.appendChild(sel);
    }
    if (get() !== "en") apply(get());
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
  // content added later (live news tabs, report builder) is translated when it appears
  let pending = false;
  new MutationObserver(() => {
    if (pending || get() === "en") return;
    pending = true;
    requestAnimationFrame(() => { pending = false; apply(get()); });
  }).observe(document.body || document.documentElement, { childList: true, subtree: true });
})();
