"""Server-side SVG charts so every chart renders without JavaScript.

Colours come from CSS custom properties (var(--series-1) …) so charts follow
the light/dark theme.
"""
from __future__ import annotations

import math
from html import escape


def _nice_ticks(lo: float, hi: float, n: int = 4) -> list[float]:
    if hi == lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.floor(lo / step) * step
    ticks, t = [], start
    while t <= hi + step * 0.001:
        ticks.append(round(t, 10))
        t += step
    if ticks[-1] < hi:      # the axis must reach the highest value, or the line runs off the chart
        ticks.append(round(t, 10))
    return ticks


def compact(v: float, decimals: int = 1) -> str:
    a = abs(v)
    if a == 0:
        return "0"
    for div, suf in ((1e12, " tn"), (1e9, " bn"), (1e6, " m"), (1e4, "k")):
        if a >= div:
            if suf == "k":
                return f"{v/1e3:,.0f}k"
            return f"{v/div:,.{decimals}f}{suf}"
    if a >= 100:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}"


def sparkline(points: list[tuple[int, float]], w: int = 120, h: int = 32, label: str = "") -> str:
    if len(points) < 2:
        return ""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    sy = (y1 - y0) or 1
    sx = (x1 - x0) or 1
    pad = 2
    pts = " ".join(f"{pad + (x - x0) / sx * (w - 2 * pad):.1f},{h - pad - (y - y0) / sy * (h - 2 * pad):.1f}"
                   for x, y in points)
    lx, ly = pts.split(" ")[-1].split(",")
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{escape(label)} trend {x0}–{x1}"><polyline points="{pts}" fill="none" '
            f'stroke="var(--series-1)" stroke-width="1.5" stroke-linejoin="round"/>'
            f'<circle cx="{lx}" cy="{ly}" r="2.2" fill="var(--series-1)"/></svg>')


def year_label(y: int) -> str:
    return f"{-y} BCE" if y < 0 else str(y)


def line_chart(series: list[dict], unit: str = "", w: int = 720, h: int = 280,
               decimals: int = 1, title: str = "", connect: bool = False, log: bool = False) -> str:
    """series: [{"label": str, "points": [(year, value)], "cls": "s1"}]"""
    series = [s for s in series if len(s["points"]) >= 1]
    if not series:
        return '<p class="muted">No data.</p>'
    all_x = [x for s in series for x, _ in s["points"]]
    all_y = [y for s in series for _, y in s["points"]]
    x0, x1 = min(all_x), max(all_x)
    lo, hi = min(all_y), max(all_y)
    if log and lo > 0:
        k0, k1 = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
        ticks = [10 ** k for k in range(k0, max(k1, k0 + 1) + 1)]
        if len(ticks) <= 3:
            ticks = sorted({m * 10 ** k for k in range(k0, k1 + 1) for m in (1, 2, 5)} | {10 ** k1})
            ticks = [t for t in ticks if 10 ** k0 <= t <= 10 ** max(k1, k0 + 1)]
        tf = math.log10
    else:
        log = False
        if not (lo > 0 and (hi - lo) / hi < 0.8):
            lo = min(lo, 0)
        ticks = _nice_ticks(lo, hi)
        tf = float
    lo, hi = tf(ticks[0]), tf(ticks[-1])
    ml, mr, mt, mb = 56, 16, 12, 28
    pw, ph = w - ml - mr, h - mt - mb
    sx = (x1 - x0) or 1

    def X(x):
        return ml + (x - x0) / sx * pw

    def Y(y):
        return mt + ph - (tf(y) - lo) / ((hi - lo) or 1) * ph

    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title or "Line chart")}">']
    for t in ticks:
        out.append(f'<line x1="{ml}" x2="{w-mr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/>')
        out.append(f'<text x="{ml-8}" y="{Y(t)+4:.1f}" class="tick" text-anchor="end">{compact(t, decimals)}</text>')
    span = x1 - x0
    step = next((s for s in (1, 5, 10, 25, 50, 100, 200, 250, 500, 1000) if span / s <= 10), 1000)
    for yr in range(math.ceil(x0 / step) * step, x1 + 1, step):
        out.append(f'<text x="{X(yr):.1f}" y="{h-8}" class="tick" text-anchor="middle">{year_label(yr)}</text>')
    for i, s in enumerate(series):
        cls = s.get("cls", f"s{i+1}")
        pts = sorted(s["points"])
        # break the line where years are missing (unless the series is sparse by design)
        segs, cur = [], [pts[0]]
        for a, b in zip(pts, pts[1:]):
            if b[0] - a[0] > 1 and not connect:
                segs.append(cur)
                cur = []
            cur.append(b)
        segs.append(cur)
        for seg in segs:
            if len(seg) == 1:
                out.append(f'<circle cx="{X(seg[0][0]):.1f}" cy="{Y(seg[0][1]):.1f}" r="2.5" class="pt {cls}"/>')
            else:
                d = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in seg)
                out.append(f'<polyline points="{d}" class="line {cls}"/>')
        lx, ly = pts[-1]
        out.append(f'<circle cx="{X(lx):.1f}" cy="{Y(ly):.1f}" r="3" class="pt {cls}"><title>{escape(s["label"])} {lx}: {compact(ly, decimals)} {escape(unit)}</title></circle>')
    out.append("</svg>")
    if len(series) > 1:
        legend = "".join(f'<span class="key"><i class="sw {s.get("cls", f"s{i+1}")}"></i>{escape(s["label"])}</span>'
                         for i, s in enumerate(series))
        out.append(f'<div class="legend">{legend}</div>')
    return "".join(out)


def succession(polities: list[dict], start: int, end: int, events: list[dict] | None = None,
               w: int = 1100, row_h: int = 18) -> str:
    """Gantt-style chart of which polities held the land, and when.

    Bar opacity follows the share of today's territory the polity held. Umbrella entities
    (empires or federations containing other polities) are drawn hollow.
    """
    label_w, pad_r, top = 210, 12, 26
    pw = w - label_w - pad_r
    n = len(polities)
    ev_h = 22 if events else 0
    h = top + n * row_h + ev_h + 8

    def X(y):
        return label_w + (y - start) / (end - start) * pw

    out = [f'<svg class="succ" viewBox="0 0 {w} {h}" role="img" aria-label="Polities that held this land, '
           f'{year_label(start)} to {end}">']
    ticks = sorted({start, 1, *range(200, end + 1, 200), end})
    for t in ticks:
        x = X(t)
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top - 6}" y2="{h - 4}" class="grid"/>')
        out.append(f'<text x="{x:.1f}" y="{top - 10}" class="tick" text-anchor="middle">{year_label(t) if t != 1 else "1 CE"}</text>')
    for i, p in enumerate(polities):
        y = top + i * row_h
        name = escape(p["name"])
        link = f'https://en.wikipedia.org/wiki/{escape(p["wikipedia"].replace(" ", "_"))}' if p.get("wikipedia") else None
        lcls = "lbl umbl" if p["umbrella"] else "lbl"
        label = f'<text x="{label_w - 8}" y="{y + row_h - 5}" class="{lcls}" text-anchor="end">{name}</text>'
        out.append(f'<a href="{link}" target="_blank" rel="noopener">{label}</a>' if link else label)
        for a, b, s in p["spans"]:
            x0, x1 = X(a), X(min(b + 5, end))
            cls = "bar umb" if p["umbrella"] else "bar"
            op = 0.3 + 0.7 * min(1.0, s)
            out.append(f'<rect x="{x0:.1f}" y="{y + 3}" width="{max(x1 - x0, 2):.1f}" height="{row_h - 6}" rx="2" '
                       f'class="{cls}" style="opacity:{op:.2f}" data-year="{a}"><title>{name}: {year_label(a)}–'
                       f'{year_label(b)}, up to {round(s * 100)}% of today’s territory</title></rect>')
    if events:
        y = top + n * row_h + 4
        out.append(f'<text x="{label_w - 8}" y="{y + 13}" class="lbl" text-anchor="end">Wars &amp; upheavals</text>')
        for e in events:
            x = X(e["start"])
            out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y + 2}" y2="{y + 18}" class="ev ev-{e["kind"]}">'
                       f'<title>{year_label(e["start"])}: {escape(e["name"])}</title></line>')
    out.append("</svg>")
    return "".join(out)


def pillar_bars(pillars: list[tuple[str, float]], w: int = 220) -> str:
    rows = []
    for i, (name, v) in enumerate(pillars):
        rows.append(f'<div class="pbar"><span>{escape(name)}</span><b style="--v:{max(0, min(100, v)):.1f}%"></b>'
                    f'<em>{v:.0f}</em></div>')
    return '<div class="pbars">' + "".join(rows) + "</div>"
