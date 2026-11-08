"""The Lab: correlations, automatic findings and data files for people who want to explore.

Everything here is descriptive. Correlations use Spearman's rank correlation on each country's
latest value from the shared ranking window; findings are candidates for a closer look, not
causal claims, and each one says how many countries it rests on.
"""
from __future__ import annotations

import json
import math
from html import escape

from . import svg
from .build_data import REF_AGE, REF_YEAR
from .config import DIST

MIN_POP = 500_000          # small states are left out of fits and movers (as in the rankings)
MIN_N = 50                 # fewest countries for a correlation to be shown
INCOME = "gdp-per-capita-ppp"

# Indicators that measure nearly the same thing. Pairs inside a family are never "surprising".
FAMILY_LISTS = {
    "income": ["gdp-per-capita-ppp", "gni-per-capita", "gni-per-capita-atlas", "average-wage"],
    "hdr": ["hdi", "ihdi", "phdi", "gdi", "gii", "inequality-loss", "expected-schooling", "mean-schooling", "life-expectancy-hdr"],
    "lifespan": ["life-expectancy", "life-expectancy-female", "life-expectancy-male", "life-expectancy-hdr"],
    "child-health": ["infant-mortality", "under5-mortality", "maternal-mortality", "stunting", "undernourishment", "tb-incidence"],
    "age": ["fertility", "birth-rate", "death-rate", "aged-0-14", "aged-65", "median-age", "dependency-ratio",
            "population-growth", "adolescent-births"],
    "wgi": ["wgi-government-effectiveness", "wgi-rule-of-law", "wgi-control-of-corruption", "wgi-regulatory-quality",
            "wgi-voice-accountability", "wgi-political-stability"],
    "poverty": ["extreme-poverty", "poverty-lmic", "poverty-umic", "gini", "top10-income-share", "inequality-loss"],
    "access": ["electricity-access", "clean-cooking", "basic-sanitation", "basic-water"],
    "renewables": ["renewable-share", "renewable-electricity"],
    "emissions": ["co2-per-capita", "ghg-per-capita", "energy-use", "material-footprint", "energy-intensity"],
    "labour": ["female-labour", "female-male-labour"],
    "structure": ["agriculture-gdp", "agri-employment", "services-gdp", "urban-share"],
    "size": ["population", "gdp", "surface-area", "patents-residents", "scientific-articles", "net-migration"],
    "school": ["mean-schooling", "expected-schooling", "secondary-enrolment", "lower-secondary-completion", "primary-completion", "literacy", "women-secondary-education",
               "tertiary-enrolment", "preprimary-enrolment"],
    "digital": ["internet-users", "fixed-broadband", "secure-servers", "mobile-subs"],
    "health-spend": ["health-spending", "health-spending-gdp", "out-of-pocket"],
    "tax": ["tax-revenue", "tax-revenue-wb"],
}

# Never offered as "surprising": income itself, composite indices built from other indicators here,
# and totals that grow with a country's size.
NOT_SURPRISING = {"income", "hdr", "size"}

# Outcomes compared with what income predicts: (indicator, fit on log scale?)
OUTCOMES = [("life-expectancy", False), ("under5-mortality", True), ("tertiary-enrolment", False),
            ("internet-users", False), ("women-parliament", False), ("co2-per-capita", True)]
# Ten-year movers: (indicator, measure change as a percentage?)
MOVERS = [("life-expectancy", False), ("under5-mortality", False), ("internet-users", False),
          ("electricity-access", False), ("renewable-electricity", False), ("women-parliament", False),
          ("gdp-per-capita-ppp", True)]


# ---------------------------------------------------------------- statistics
def ranks(xs: list[float]) -> list[float]:
    """Average ranks (1-based), ties share the mean rank."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = r
        i = j + 1
    return out


def pearson(x: list[float], y: list[float]) -> float | None:
    n = len(x)
    if n < 3:
        return None
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(x: list[float], y: list[float]) -> float | None:
    return pearson(ranks(x), ranks(y))


def partial(rxy: float, rxz: float, ryz: float) -> float | None:
    """Correlation of x and y once z (here: income) is held constant."""
    d = (1 - rxz ** 2) * (1 - ryz ** 2)
    return None if d <= 0 else (rxy - rxz * ryz) / math.sqrt(d)


def ols(x: list[float], y: list[float]) -> tuple[float, float, float]:
    """Least-squares line y = a + b x, and R²."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    a = my - b * mx
    ss_res = sum((c - (a + b * v)) ** 2 for v, c in zip(x, y))
    ss_tot = sum((c - my) ** 2 for c in y)
    return a, b, (1 - ss_res / ss_tot) if ss_tot else 0.0


def leaf_order(names: list[str], dist: list[list[float]]) -> list[int]:
    """Average-linkage clustering; returns the leaf order so related indicators sit together."""
    clusters = {i: [i] for i in range(len(names))}
    while len(clusters) > 1:
        keys = list(clusters)
        best, pair = None, None
        for a_i, a in enumerate(keys):
            for b in keys[a_i + 1:]:
                d = sum(dist[i][j] for i in clusters[a] for j in clusters[b]) / (len(clusters[a]) * len(clusters[b]))
                if best is None or d < best:
                    best, pair = d, (a, b)
        a, b = pair
        clusters[a] = clusters[a] + clusters.pop(b)
    return next(iter(clusters.values()))


# ---------------------------------------------------------------- static charts
def scatter_svg(points: list[dict], xlab: str, ylab: str, xlog: bool, ylog: bool, line=None,
                w: int = 560, h: int = 340, title: str = "") -> str:
    """points: [{x, y, hl: 'up'|'down'|None, label}]; line: (a, b) on the transformed axes."""
    tx = (lambda v: math.log10(v)) if xlog else (lambda v: v)
    ty = (lambda v: math.log10(v)) if ylog else (lambda v: v)
    xs = [tx(p["x"]) for p in points]
    ys = [ty(p["y"]) for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    padx, pady = (x1 - x0) * .04 or 1, (y1 - y0) * .06 or 1
    x0, x1, y0, y1 = x0 - padx, x1 + padx, y0 - pady, y1 + pady
    ml, mr, mt, mb = 52, 14, 12, 40
    pw, ph = w - ml - mr, h - mt - mb
    X = lambda v: ml + (v - x0) / (x1 - x0) * pw
    Y = lambda v: mt + ph - (v - y0) / (y1 - y0) * ph

    def ticks(lo, hi, log):
        if log:
            return [k for k in range(math.ceil(lo), math.floor(hi) + 1)]
        return [t for t in svg._nice_ticks(lo, hi) if lo <= t <= hi]

    out = [f'<svg class="chart lab-scatter" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title or ylab + " against " + xlab)}">']
    for t in ticks(y0, y1, ylog):
        out.append(f'<line x1="{ml}" x2="{w - mr}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/>'
                   f'<text x="{ml - 6}" y="{Y(t) + 4:.1f}" class="tick" text-anchor="end">{svg.compact(10 ** t if ylog else t, 1)}</text>')
    for t in ticks(x0, x1, xlog):
        out.append(f'<text x="{X(t):.1f}" y="{h - 22}" class="tick" text-anchor="middle">{svg.compact(10 ** t if xlog else t, 1)}</text>')
    out.append(f'<text x="{ml + pw / 2:.0f}" y="{h - 4}" class="tick axis-label" text-anchor="middle">{escape(xlab)}{" (log)" if xlog else ""}</text>')
    if line:
        a, b = line
        out.append(f'<line x1="{X(x0):.1f}" y1="{Y(a + b * x0):.1f}" x2="{X(x1):.1f}" y2="{Y(a + b * x1):.1f}" class="fit"/>')
    for p, x, y in sorted(zip(points, xs, ys), key=lambda t: t[0].get("hl") is not None):
        cls = f"dot {p['hl']}" if p.get("hl") else "dot"
        out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{4.2 if p.get("hl") else 3}" class="{cls}"><title>{escape(p["label"])}</title></circle>')
        if p.get("hl"):
            anchor = "end" if X(x) > w - 110 else "start"
            dx = -7 if anchor == "end" else 7
            out.append(f'<text x="{X(x) + dx:.1f}" y="{Y(y) + 4:.1f}" class="dot-label" text-anchor="{anchor}">{escape(p["label"])}</text>')
    out.append(f'<text x="{ml}" y="{mt - 2}" class="tick axis-label">{escape(ylab)}{" (log)" if ylog else ""}</text>')
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------- the lab
class Lab:
    def __init__(self, site):
        self.site, m = site, site.m
        self.m = m
        self.countries = site.countries
        self.inds = [i for i in m.indicators.values()
                     if i["source"] != "gdelt" and not m.sources.get(i["source"], {}).get("no_modification")
                     and not i.get("display_only")]
        self.by_ind = {i["id"]: i for i in self.inds}
        self.pop = {}
        for c in self.countries:
            p = m.latest(c["entity_id"], "population")
            self.pop[c["entity_id"]] = p[1] if p else None
        self.latest: dict[str, dict[str, tuple[int, float]]] = {}
        for i in self.inds:
            vals = {}
            for c in self.countries:
                lt = m.latest(c["entity_id"], i["id"], max_year=REF_YEAR, min_year=REF_YEAR - REF_AGE)
                if lt:
                    vals[c["entity_id"]] = (lt[0], lt[1])
            self.latest[i["id"]] = vals
        self.family = {}
        for fam, ids in FAMILY_LISTS.items():
            for x in ids:
                self.family.setdefault(x, set()).add(fam)

    def name(self, iso3: str) -> str:
        return self.site.by_id[iso3]["name"]

    def pair(self, a: str, b: str, big_only: bool = False) -> tuple[list[str], list[float], list[float]]:
        va, vb = self.latest[a], self.latest[b]
        keys = sorted(k for k in va.keys() & vb.keys() if not big_only or (self.pop.get(k) or 0) >= MIN_POP)
        return keys, [va[k][1] for k in keys], [vb[k][1] for k in keys]

    def related(self, a: str, b: str) -> bool:
        return bool(self.family.get(a, set()) & self.family.get(b, set())) or \
            self.by_ind[a]["dimension"] == self.by_ind[b]["dimension"]

    # ---- correlation matrix
    def correlations(self) -> dict:
        ids = [i["id"] for i in self.inds]
        n = len(ids)
        rho = [[None] * n for _ in range(n)]
        cnt = [[0] * n for _ in range(n)]
        for i in range(n):
            rho[i][i], cnt[i][i] = 1.0, len(self.latest[ids[i]])
            for j in range(i + 1, n):
                keys, x, y = self.pair(ids[i], ids[j])
                cnt[i][j] = cnt[j][i] = len(keys)
                if len(keys) >= MIN_N:
                    r = spearman(x, y)
                    rho[i][j] = rho[j][i] = None if r is None else round(r, 3)
        dist = [[1 - abs(rho[i][j]) if rho[i][j] is not None else 1.0 for j in range(n)] for i in range(n)]
        order = leaf_order(ids, dist)
        self.rho = {(ids[i], ids[j]): rho[i][j] for i in range(n) for j in range(n)}
        self.cnt = {(ids[i], ids[j]): cnt[i][j] for i in range(n) for j in range(n)}
        return {"release": self.m.release, "method": "Spearman rank correlation of each country's latest value "
                f"from {REF_YEAR - REF_AGE} to {REF_YEAR}; pairs with fewer than {MIN_N} countries are blank.",
                "ids": [ids[k] for k in order], "names": [self.by_ind[ids[k]]["name"] for k in order],
                "dims": [self.by_ind[ids[k]]["dimension"] for k in order],
                "rho": [[rho[i][j] for j in order] for i in order], "n": [[cnt[i][j] for j in order] for i in order]}

    # ---- findings
    def performers(self) -> list[dict]:
        out = []
        for ind_id, ylog in OUTCOMES:
            if ind_id not in self.by_ind or INCOME not in self.by_ind:
                continue
            keys, inc, y = self.pair(INCOME, ind_id, big_only=True)
            keep = [k for k, a, b in zip(keys, inc, y) if a > 0 and (b > 0 or not ylog)]
            keys2 = [k for k in keys if k in keep]
            if len(keys2) < MIN_N:
                continue
            lx = [math.log10(self.latest[INCOME][k][1]) for k in keys2]
            ly = [math.log10(self.latest[ind_id][k][1]) if ylog else self.latest[ind_id][k][1] for k in keys2]
            a, b, r2 = ols(lx, ly)
            res = {k: yv - (a + b * xv) for k, xv, yv in zip(keys2, lx, ly)}
            ind = self.by_ind[ind_id]
            better = -1 if ind["direction"] == "lower_better" else 1
            ranked = sorted(keys2, key=lambda k: better * res[k], reverse=True)
            top, bottom = ranked[:4], ranked[-4:][::-1]

            def describe(k):
                actual = self.latest[ind_id][k][1]
                pred = 10 ** (a + b * math.log10(self.latest[INCOME][k][1]))
                if not ylog:
                    pred = a + b * math.log10(self.latest[INCOME][k][1])
                gap = (actual / pred - 1) * 100 if ylog else actual - pred
                return {"iso3": k, "name": self.name(k), "slug": self.site.by_id[k]["slug"], "actual": actual,
                        "expected": pred, "gap": gap, "gap_pct": ylog, "year": self.latest[ind_id][k][0]}

            pts = [{"x": self.latest[INCOME][k][1], "y": self.latest[ind_id][k][1], "label": self.name(k),
                    "hl": "up" if k in top else "down" if k in bottom else None} for k in keys2]
            out.append({"kind": "performers", "indicator": ind_id, "name": ind["name"], "unit": ind["unit"],
                        "decimals": ind.get("decimals", 1), "n": len(keys2), "r2": r2, "ylog": ylog,
                        "lower_better": ind["direction"] == "lower_better",
                        "above": [describe(k) for k in top], "below": [describe(k) for k in bottom],
                        "chart": scatter_svg(pts, self.by_ind[INCOME]["name"], ind["name"], True, ylog, (a, b),
                                             title=f"{ind['name']} against income per person"),
                        "scatter": f"/lab/scatter/#x={INCOME}&y={ind_id}&lx=1&ly={int(ylog)}"})
        return out

    def movers(self) -> list[dict]:
        out = []
        for ind_id, pct in MOVERS:
            if ind_id not in self.by_ind:
                continue
            ind = self.by_ind[ind_id]
            rows = []
            for c in self.countries:
                e = c["entity_id"]
                if (self.pop.get(e) or 0) < MIN_POP or e not in self.latest[ind_id]:
                    continue
                y1, v1 = self.latest[ind_id][e]
                past = {y: v for y, v, _ in self.m.series(e, ind_id)}
                y0 = next((y for y in (y1 - 10, y1 - 11, y1 - 9) if y in past), None)
                if y0 is None:
                    continue
                v0 = past[y0]
                if pct:
                    if v0 <= 0:
                        continue
                    ch = (v1 / v0 - 1) * 100
                else:
                    ch = v1 - v0
                rows.append({"iso3": e, "name": c["name"], "slug": c["slug"], "y0": y0, "v0": v0, "y1": y1, "v1": v1, "change": ch})
            if len(rows) < MIN_N:
                continue
            sign = -1 if ind["direction"] == "lower_better" else 1
            rows.sort(key=lambda r: sign * r["change"], reverse=True)
            out.append({"kind": "movers", "indicator": ind_id, "name": ind["name"], "unit": ind["unit"],
                        "decimals": ind.get("decimals", 1), "pct": pct, "n": len(rows),
                        "lower_better": ind["direction"] == "lower_better",
                        "best": rows[:5], "worst": rows[-5:][::-1],
                        "median": sorted(r["change"] for r in rows)[len(rows) // 2]})
        return out

    def links(self, limit: int = 10) -> list[dict]:
        """Strong relationships between unrelated indicators that survive holding income constant."""
        ids = [i["id"] for i in self.inds if i["id"] != INCOME]
        cands = []
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                r = self.rho.get((a, b))
                if r is None or abs(r) < .45 or self.related(a, b) or NOT_SURPRISING & (self.family.get(a, set()) | self.family.get(b, set())):
                    continue
                keys = sorted(self.latest[a].keys() & self.latest[b].keys() & self.latest[INCOME].keys())
                if len(keys) < 80:
                    continue
                x = [self.latest[a][k][1] for k in keys]
                y = [self.latest[b][k][1] for k in keys]
                z = [self.latest[INCOME][k][1] for k in keys]
                rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
                p = partial(rxy, rxz, ryz)
                if p is None or abs(p) < .35:
                    continue
                cands.append({"a": a, "b": b, "rho": rxy, "partial": p, "n": len(keys), "rxz": rxz, "ryz": ryz})
        cands.sort(key=lambda c: abs(c["partial"]), reverse=True)
        picked, used = [], {}
        for c in cands:                     # keep the list varied: each indicator at most twice
            if used.get(c["a"], 0) >= 2 or used.get(c["b"], 0) >= 2:
                continue
            used[c["a"]] = used.get(c["a"], 0) + 1
            used[c["b"]] = used.get(c["b"], 0) + 1
            A, B = self.by_ind[c["a"]], self.by_ind[c["b"]]
            la, lb = A.get("transform") == "log", B.get("transform") == "log"
            keys, x, y = self.pair(c["a"], c["b"])
            pts = [{"x": xv, "y": yv, "label": self.name(k), "hl": None} for k, xv, yv in zip(keys, x, y)
                   if (xv > 0 or not la) and (yv > 0 or not lb)]
            picked.append({**c, "kind": "link", "a_name": A["name"], "b_name": B["name"],
                           "a_dim": A["dimension"], "b_dim": B["dimension"],
                           "chart": scatter_svg(pts, A["name"], B["name"], la, lb, w=460, h=300),
                           "scatter": f"/lab/scatter/#x={c['a']}&y={c['b']}&lx={int(la)}&ly={int(lb)}"})
            if len(picked) >= limit:
                break
        return picked

    # ---- outputs
    def meta(self) -> dict:
        return {"release": self.m.release, "reference_year": REF_YEAR, "max_data_age": REF_AGE,
                "entities": [{"id": c["entity_id"], "name": c["name"], "slug": c["slug"], "region": c.get("region"),
                              "income": c.get("income"), "pop": self.pop.get(c["entity_id"])} for c in self.countries],
                "indicators": [{"id": i["id"], "name": i["name"], "unit": i["unit"], "dim": i["dimension"],
                                "log": i.get("transform") == "log", "decimals": i.get("decimals", 1),
                                "direction": i["direction"], "source": i["source"]} for i in self.inds]}

    def build(self) -> dict:
        corr = self.correlations()
        findings = {"performers": self.performers(), "movers": self.movers(), "links": self.links()}
        out = DIST / "lab"
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(json.dumps(self.meta(), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        (out / "correlations.json").write_text(json.dumps(corr, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        plain = {k: [{kk: vv for kk, vv in f.items() if kk != "chart"} for f in v] for k, v in findings.items()}
        (out / "findings.json").write_text(json.dumps({"release": self.m.release, **plain}, ensure_ascii=False,
                                                      separators=(",", ":"), default=float), encoding="utf-8")
        return {"corr": corr, "findings": findings}
