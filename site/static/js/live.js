/* Live world estimates. A port of pipeline/live.py estimate(); tests compare the two. */
(function (root) {
  "use strict";

  function estimate(b, nowMs) {
    const yearMs = 365.2425 * 24 * 3600 * 1000;
    const t0 = Date.UTC(b.population_year, 6, 1);              // the population figure is mid-year
    const rate = (b.birth_rate - b.death_rate) / 1000;
    const pop = b.population * Math.exp(rate * (nowMs - t0) / yearMs);
    const year = new Date(nowMs).getUTCFullYear();
    const start = Date.UTC(year, 0, 1), end = Date.UTC(year + 1, 0, 1);
    const frac = (nowMs - start) / (end - start);
    const births = b.birth_rate / 1000 * pop * frac;
    const deaths = b.death_rate / 1000 * pop * frac;
    const co2 = b.co2_pc === null || b.co2_pc === undefined ? null : b.co2_pc * pop * frac;
    return { population: pop, births, deaths, growth: births - deaths, co2 };
  }

  if (typeof module !== "undefined" && module.exports) { module.exports = { estimate }; return; }

  const el = document.getElementById("live-data");
  if (!el) return;
  const base = JSON.parse(el.textContent);
  const fields = Array.from(document.querySelectorAll("[data-live]"));
  const tick = () => {
    const v = estimate(base, Date.now());
    for (const f of fields) {
      const x = v[f.dataset.live];
      if (x !== null && x !== undefined) f.textContent = Math.round(x).toLocaleString("en");
    }
  };
  tick();
  setInterval(tick, 1000);
})(typeof window !== "undefined" ? window : globalThis);
