/* One number formatter for the browser: mirrors pipeline/numfmt.py so values look the same whether a page was
   built in Python or drawn in the browser. Every script formats numbers for display through window.NF.
   NF.value(v, decimals, unit)  tables and text: "1.46 bn", "$984.0 bn", "72.1", "12,345"
   NF.scale(v, decimals)         labels and axes: "1.5 bn", "312 m", "45k", "72.1"
   NF.compact(v, unit)           tiles: 1.4B, 312M, $12.3k, 7.1%
   NF.int(v)                     whole numbers with separators: "8,123,456,789"
   NF.signed(v, decimals)        "+1.2" / "−0.4" (a real minus sign) */
(() => {
  const loc = "en";
  const fixed = (v, d) => Number(v).toLocaleString(loc, { minimumFractionDigits: d, maximumFractionDigits: d });
  function scale(v, d = 1) {
    const a = Math.abs(v);
    if (!a) return "0";
    for (const [div, suf] of [[1e12, " tn"], [1e9, " bn"], [1e6, " m"], [1e4, "k"]]) {
      if (a >= div) return suf === "k" ? fixed(v / 1e3, 0) + "k" : fixed(v / div, d) + suf;
    }
    return a >= 100 ? fixed(v, 0) : fixed(v, d);
  }
  function value(v, d = 2, unit = "") {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    let s = Math.abs(v) >= 1e6 ? scale(v, Math.abs(v) < 1e10 ? 2 : 1) : fixed(v, d);
    if (unit.startsWith("current US$") && !unit.endsWith("person")) s = "$" + s;
    return s;
  }
  function compact(v, unit = "", d = null) {
    if (v === null || v === undefined || !isFinite(v)) return "—";
    const a = Math.abs(v), sign = v < 0 ? "−" : "";
    if (unit.startsWith("%")) return sign + a.toFixed(d === null ? 1 : Math.min(d, 1)) + "%";
    const money = /US\$|international \$|^\$/.test(unit) ? "$" : "";
    for (const [size, suf] of [[1e12, "T"], [1e9, "B"], [1e6, "M"], [1e3, "k"]]) {
      if (a >= size) { const n = a / size; return sign + money + (n >= 100 ? n.toFixed(0) : String(+n.toFixed(1))) + suf; }
    }
    return sign + money + fixed(a, d === null ? (a >= 100 ? 0 : a >= 10 ? 1 : 2) : d);
  }
  const int = v => fixed(Math.round(v), 0);
  // labels and tooltips: words for large numbers, up to `d` decimals (trailing zeros dropped) for small ones
  const label = (v, d = 2) => Math.abs(v) >= 100 ? scale(v, 1) : Number(v).toLocaleString(loc, { maximumFractionDigits: d });
  const signed = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + fixed(Math.abs(v), d);
  window.NF = { value, scale, compact, int, signed, label };
})();
