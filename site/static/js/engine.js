/* Browser port of pipeline/engine.py. Keep the two in step:
   tests/test_parity.py runs this file under Node and compares results. */
(function (root) {
  "use strict";
  const LOWER = "lower_better";

  function transform(v, t) {
    if (t === "log") return v > 0 ? Math.log(v) : null;
    return v;
  }

  function normalise(values, method, direction, t) {
    const tv = {};
    for (const [e, v] of Object.entries(values)) { const x = transform(v, t); if (x !== null) tv[e] = x; }
    const xs = Object.values(tv);
    if (!xs.length) return {};
    const out = {};
    if (method === "z_score") {
      const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
      const sd = Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length) || 1;
      for (const [e, v] of Object.entries(tv)) out[e] = Math.min(1, Math.max(0, ((v - mean) / sd + 3) / 6));
    } else {
      const lo = Math.min(...xs), hi = Math.max(...xs), span = hi - lo;
      for (const [e, v] of Object.entries(tv)) out[e] = span ? (v - lo) / span : 0.5;
    }
    if (direction === LOWER) for (const e in out) out[e] = 1 - out[e];
    return out;
  }

  function wmean(pairs, geometric) {
    const total = pairs.reduce((a, p) => a + p[1], 0);
    if (geometric) return Math.exp(pairs.reduce((a, [s, w]) => a + w * Math.log(Math.max(s, 0.001)), 0) / total);
    return pairs.reduce((a, [s, w]) => a + s * w, 0) / total;
  }

  const round = (x, d) => { const f = 10 ** d; return Math.round(x * f) / f; };

  /* indicators: [{id, weight, pillar}], pillars: [{id, weight}] */
  function score(norm, indicators, pillars, entities, minCoverage, aggregation) {
    const pw = Object.fromEntries(pillars.map(p => [p.id, p.weight]));
    const geometric = aggregation === "geometric";
    const pillarTotal = pillars.reduce((a, p) => a + p.weight, 0);
    const byPillar = {};
    for (const i of indicators) (byPillar[i.pillar] = byPillar[i.pillar] || []).push(i);
    const pit = {};
    for (const [p, inds] of Object.entries(byPillar)) pit[p] = inds.reduce((a, i) => a + i.weight, 0);
    const results = [];
    for (const e of entities) {
      const ps = {}; let coverage = 0;
      for (const [p, inds] of Object.entries(byPillar)) {
        const pairs = inds.filter(i => norm[i.id] && e in norm[i.id]).map(i => [norm[i.id][e], i.weight]);
        if (!pairs.length) continue;
        coverage += (pw[p] / pillarTotal) * pairs.reduce((a, x) => a + x[1], 0) / pit[p];
        ps[p] = wmean(pairs, geometric);
      }
      coverage = round(coverage, 9);
      if (coverage < minCoverage) { results.push({ entity_id: e, score: null, coverage, excluded_reason: "coverage_below_threshold", pillar_scores: {} }); continue; }
      const total = wmean(Object.entries(ps).map(([p, s]) => [s, pw[p]]), geometric);
      const pillar_scores = {}; for (const [p, s] of Object.entries(ps)) pillar_scores[p] = round(s * 100, 6);
      results.push({ entity_id: e, score: round(total * 100, 6), coverage, excluded_reason: null, pillar_scores });
    }
    return assignRanks(results);
  }

  function assignRanks(results, descending = true) {
    const ranked = results.filter(r => r.score !== null);
    ranked.sort((a, b) => (descending ? b.score - a.score : a.score - b.score) || (a.entity_id < b.entity_id ? -1 : a.entity_id > b.entity_id ? 1 : 0));
    let prev = null, prevRank = 0;
    ranked.forEach((r, i) => {
      const key = round(r.score, 6);
      if (key === prev) r.rank = prevRank; else { r.rank = i + 1; prevRank = i + 1; prev = key; }
    });
    const counts = {}; ranked.forEach(r => { counts[r.rank] = (counts[r.rank] || 0) + 1; });
    ranked.forEach(r => { r.is_tied = counts[r.rank] > 1; });
    const unranked = results.filter(r => r.score === null).sort((a, b) => (a.entity_id < b.entity_id ? -1 : 1));
    unranked.forEach(r => { r.rank = null; r.is_tied = false; });
    return ranked.concat(unranked);
  }

  /* Seeded PRNG, so a given index always shows the same range. */
  function mulberry32(a) {
    return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  }

  /* Like engine.sensitivity in Python: shake every weight by up to +-spread, re-rank, return the
     5th-95th percentile rank per entity. Fewer runs than the published indices, as it runs live. */
  function sensitivity(norm, indicators, pillars, entities, minCoverage, aggregation, runs, spread, seed) {
    const rng = mulberry32(seed), ranks = {};
    const shake = w => w * (1 - spread + rng() * 2 * spread);
    for (let n = 0; n < runs; n++) {
      const ps = pillars.map(p => ({ ...p, weight: shake(p.weight) }));
      const is = indicators.map(i => ({ ...i, weight: shake(i.weight) }));
      for (const r of score(norm, is, ps, entities, minCoverage, aggregation)) if (r.rank) (ranks[r.entity_id] = ranks[r.entity_id] || []).push(r.rank);
    }
    const out = {};
    for (const [e, rs] of Object.entries(ranks)) {
      rs.sort((a, b) => a - b);
      out[e] = [rs[Math.floor(0.05 * (rs.length - 1))], rs[Math.ceil(0.95 * (rs.length - 1))]];
    }
    return out;
  }

  const api = { normalise, score, assignRanks, sensitivity };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.AtlasEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
