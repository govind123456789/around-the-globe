"""Reports: global trend reports written from the data (data/reports.yaml), and the per-country
files behind the custom report builder.

Every sentence is generated from the release's own numbers, so reports update with each release
and never contain a figure that was typed by hand. Section kinds:
  world_trend  the source's world series, first and latest value, and any peak in between
  leaders      top 10 and bottom 5 countries of at least a million people
  movers       biggest changes over N years (points for rates, % for amounts)
  shares       the largest countries' shares of a world total over time
  regions      regional sums (amounts) or population-weighted averages (rates)
  gap          the spread between the 90th and 10th percentile countries over time
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import svg
from .config import load_yaml
from .markets import UNIT_SUFFIX

MIN_POP = 1e6
ADDITIVE_UNITS = {"current US$", "tonnes", "TWh", "GW", "passengers", "TEU", "people", "companies",
                  "registrations", "million tonne-km", "MtCO₂e", "applications"}


def lc(name: str) -> str:
    """Lower-case a name's first letter for use mid-sentence, but keep acronyms (GDP, CO₂) intact."""
    return name if name[:2].isupper() else name[0].lower() + name[1:]


def additive(ind: dict) -> bool:
    name = ind["name"].lower()
    return ind["unit"] in ADDITIVE_UNITS and "per capita" not in name and "per person" not in name


def relative(ind: dict) -> bool:
    """Amounts change by a percentage; rates and scores change by points."""
    return additive(ind) or "$" in ind["unit"]


class Reports:
    def __init__(self, model, countries: list[dict], by_id: dict, show):
        self.m, self.countries, self.by_id, self.show = model, countries, by_id, show
        self.pop = {e["entity_id"]: (model.latest(e["entity_id"], "population") or (0, 0, ""))[1] for e in countries}
        self.big = [e for e in countries if self.pop.get(e["entity_id"], 0) >= MIN_POP]
        self.regions = {g: [x for x in mem if x in self.pop] for g, mem in model.groups.items()
                        if by_id[g].get("group_kind") == "region"}
        cfg = load_yaml("reports.yaml")
        self.reports = []
        for r in cfg["reports"]:
            secs = [s for s in (self.section(x) for x in r["sections"] if x["indicator"] in model.indicators) if s]
            if secs:
                self.reports.append({**r, "sections": secs, "findings": [s["finding"] for s in secs if s.get("finding")],
                                     "inds": sorted({s["ind"]["id"] for s in secs})})

    # ------------------------------------------------------------------ helpers
    def ind(self, i: str) -> dict:
        return self.m.indicators[i]

    def v(self, x: float, ind: dict) -> str:
        return self.show(x, ind)

    def delta(self, a: float, b: float, ind: dict) -> str:
        if relative(ind):
            return f"{100 * (b - a) / a:+.0f}%" if a else "—"
        d = b - a
        dec = ind.get("decimals", 1)
        unit = ind["unit"]
        if unit.startswith("%"):
            return f"{d:+.{dec}f} points"
        return f"{d:+,.{dec}f}{UNIT_SUFFIX.get(unit, ' ' + unit if len(unit) < 14 else '')}"

    def change(self, a: float, b: float, ind: dict) -> float:
        return (b - a) / abs(a) if relative(ind) and a else (b - a)

    def world(self, i: str, since: int = 1990) -> list[tuple[int, float]]:
        return [(y, v) for y, v, _ in self.m.series("WLD", i) if y >= since]

    def at(self, eid: str, i: str, year: int, slack: int = 0):
        ser = {y: v for y, v, _ in self.m.series(eid, i)}
        for d in range(slack + 1):
            for y in (year - d, year + d):
                if y in ser:
                    return y, ser[y]
        return None

    def latest_rows(self, i: str, pool=None):
        pool = pool if pool is not None else (self.pool if getattr(self, "pool", None) is not None else self.big)
        rows = [(e, lt) for e in pool if (lt := self.m.latest(e["entity_id"], i, min_year=2015))]
        if not rows:
            return []
        top_year = max(lt[0] for _, lt in rows)
        return [(e, lt[0], lt[1]) for e, lt in rows if lt[0] >= top_year - 4]

    def best_first(self, ind: dict) -> bool:
        return ind["direction"] != "lower_better"

    # ------------------------------------------------------------------ sections
    def section(self, s: dict) -> dict | None:
        fn = getattr(self, "s_" + s["kind"])
        out = fn(self.ind(s["indicator"]), s)
        if out:
            out.update({"kind": s["kind"], "ind": self.ind(s["indicator"]), "title": s.get("title") or out.get("title")})
        return out

    def s_world_trend(self, ind: dict, s: dict):
        pts = self.world(ind["id"], s.get("since", 2000))
        if len(pts) < 2:
            return None
        (y0, v0), (y1, v1) = pts[0], pts[-1]
        rose = v1 > v0
        good = rose == (ind["direction"] == "higher_better") if ind["direction"] != "neutral" else None
        verb = "rose" if rose else "fell"
        text = [f"Worldwide, {lc(ind['name'])} {verb} from {self.v(v0, ind)} in {y0} to {self.v(v1, ind)} in {y1} "
                f"({self.delta(v0, v1, ind)})."]
        peak = max(pts, key=lambda p: p[1]) if rose else min(pts, key=lambda p: p[1])
        low = min(pts, key=lambda p: p[1]) if rose else max(pts, key=lambda p: p[1])
        if peak[0] not in (y0, y1):
            text.append(f"It {'peaked' if rose else 'bottomed out'} at {self.v(peak[1], ind)} in {peak[0]}.")
        elif low[0] not in (y0, y1):
            text.append(f"It dipped to {self.v(low[1], ind)} in {low[0]} before {'recovering' if rose else 'falling further'}.")
        recent = [p for p in pts if p[0] >= y1 - 5]
        if len(recent) >= 2 and recent[0][0] != y0:
            text.append(f"Over the last five years the change was {self.delta(recent[0][1], recent[-1][1], ind)}.")
        if good is not None:
            text.append("That is an improvement." if good else "That is a move in the wrong direction.")
        chart = svg.line_chart([{"label": "World", "points": pts}], ind["unit"], decimals=ind.get("decimals", 1),
                               title=f"{ind['name']}, world")
        return {"text": text, "chart": chart, "big": self.v(v1, ind), "big_label": f"{ind['name']}, world, {y1}",
                "finding": f"World {lc(ind['name'])} {verb} from {self.v(v0, ind)} to {self.v(v1, ind)} ({y0}–{y1}).",
                "title": f"The world trend in {lc(ind['name'])}"}

    def s_leaders(self, ind: dict, s: dict):
        rows = self.latest_rows(ind["id"])
        if len(rows) < 10:
            return None
        rows.sort(key=lambda r: r[2], reverse=self.best_first(ind))
        top, bottom = rows[:10], rows[-5:][::-1]
        med = statistics.median(r[2] for r in rows)
        word = "highest" if ind["direction"] != "lower_better" else "lowest"
        t = top
        text = [f"{t[0][0]['name']} has the {word} {lc(ind['name'])} at {self.v(t[0][2], ind)}, followed by "
                f"{t[1][0]['name']} ({self.v(t[1][2], ind)}) and {t[2][0]['name']} ({self.v(t[2][2], ind)}).",
                f"At the other end are {bottom[0][0]['name']} ({self.v(bottom[0][2], ind)}) and "
                f"{bottom[1][0]['name']} ({self.v(bottom[1][2], ind)}). The median of {len(rows)} countries is {self.v(med, ind)}."]
        peak = max(abs(r[2]) for r in top) or 1
        bars = [{"e": e, "year": y, "text": self.v(v, ind), "bar": round(100 * abs(v) / peak, 1), "rank": k + 1}
                for k, (e, y, v) in enumerate(top)]
        return {"text": text, "bars": bars, "bottom": [{"e": e, "year": y, "text": self.v(v, ind)} for e, y, v in bottom],
                "big": t[0][0]["name"], "big_label": f"{word.capitalize()} {lc(ind['name'])}",
                "finding": f"{t[0][0]['name']} has the {word} {lc(ind['name'])} ({self.v(t[0][2], ind)}).",
                "title": f"Who leads in {lc(ind['name'])}"}

    def s_movers(self, ind: dict, s: dict):
        years = s.get("years", 10)
        rows = []
        for e, y1, v1 in self.latest_rows(ind["id"]):
            base = self.at(e["entity_id"], ind["id"], y1 - years, slack=1)
            if base and (not relative(ind) or base[1] > 0):
                rows.append({"e": e, "y0": base[0], "v0": base[1], "y1": y1, "v1": v1,
                             "c": self.change(base[1], v1, ind), "d": self.delta(base[1], v1, ind)})
        if len(rows) < 10:
            return None
        rows.sort(key=lambda r: r["c"], reverse=ind["direction"] != "lower_better")
        up, down = rows[:6], rows[-5:][::-1]
        good = "improvement" if ind["direction"] != "neutral" else "increase"
        bad = "deterioration" if ind["direction"] != "neutral" else "decrease"
        u = up
        text = [f"Over about {years} years, the biggest {good} in {lc(ind['name'])} was in {u[0]['e']['name']}, "
                f"from {self.v(u[0]['v0'], ind)} in {u[0]['y0']} to {self.v(u[0]['v1'], ind)} in {u[0]['y1']} ({u[0]['d']}).",
                f"{u[1]['e']['name']} ({u[1]['d']}) and {u[2]['e']['name']} ({u[2]['d']}) follow.",
                f"The largest {bad} was in {down[0]['e']['name']} ({down[0]['d']}), then {down[1]['e']['name']} ({down[1]['d']})."]
        for r in up + down:
            r["from"], r["to"] = self.v(r["v0"], ind), self.v(r["v1"], ind)
        return {"text": text, "up": up, "down": down, "years": years, "big": u[0]["d"],
                "big_label": f"{u[0]['e']['name']}, {u[0]['y0']}–{u[0]['y1']}",
                "finding": f"{u[0]['e']['name']} saw the biggest {good} in {lc(ind['name'])} over {years} years ({u[0]['d']}).",
                "title": f"Biggest movers in {lc(ind['name'])}"}

    def s_shares(self, ind: dict, s: dict):
        world = dict(self.world(ind["id"], s.get("since", 2000)))
        rows = self.latest_rows(ind["id"], pool=self.countries)
        if not world or len(rows) < 5:
            return None
        rows.sort(key=lambda r: -r[2])
        series, notes = [], []
        for k, (e, y, v) in enumerate(rows[:5]):
            pts = [(yy, 100 * vv / world[yy]) for yy, vv, _ in self.m.series(e["entity_id"], ind["id"])
                   if yy in world and world[yy] > 0]
            if len(pts) >= 2:
                series.append({"label": e["name"], "points": pts, "cls": f"s{k + 1}"})
                notes.append((e, pts[0], pts[-1]))
        if not notes:
            return None
        top5 = sum(100 * v / world[y] for e, y, v in rows[:5] if y in world)
        e, (ya, a), (yb, b) = notes[0]
        mover = max(notes, key=lambda n: n[2][1] - n[1][1])
        text = [f"The five largest countries hold {top5:.0f}% of world {lc(ind['name'])}.",
                f"{e['name']}'s share moved from {a:.1f}% in {ya} to {b:.1f}% in {yb}."]
        if mover[0] is not e:
            text.append(f"Among the five, {mover[0]['name']} gained most: from {mover[1][1]:.1f}% in {mover[1][0]} "
                        f"to {mover[2][1]:.1f}% in {mover[2][0]}.")
        loser = min(notes, key=lambda n: n[2][1] - n[1][1])
        if loser[2][1] < loser[1][1]:
            text.append(f"{loser[0]['name']}'s share fell from {loser[1][1]:.1f}% to {loser[2][1]:.1f}%.")
        chart = svg.line_chart(series, "% of world", decimals=1, title=f"Share of world {lc(ind['name'])}")
        return {"text": text, "chart": chart, "big": f"{top5:.0f}%", "big_label": f"Top five countries' share of the world",
                "finding": f"{e['name']} holds {b:.1f}% of world {lc(ind['name'])}, {'up' if b >= a else 'down'} from {a:.1f}% in {ya}.",
                "title": f"Who holds the world's {lc(ind['name'])}"}

    def s_regions(self, ind: dict, s: dict):
        out = []
        for g, members in self.regions.items():
            vals = [(x, lt) for x in members if (lt := self.m.latest(x, ind["id"], min_year=2015))]
            if len(vals) < 3:
                continue
            if additive(ind):
                val = sum(lt[1] for _, lt in vals)
            else:
                w = [(self.pop.get(x, 0), lt[1]) for x, lt in vals if self.pop.get(x, 0) > 0]
                tot = sum(p for p, _ in w)
                if not tot:
                    continue
                val = sum(p * v for p, v in w) / tot
            out.append({"g": self.by_id[g], "value": val, "text": self.v(val, ind), "n": len(vals), "of": len(members)})
        if len(out) < 3:
            return None
        out.sort(key=lambda r: r["value"], reverse=True)
        peak = max(abs(r["value"]) for r in out) or 1
        for r in out:
            r["bar"] = round(100 * abs(r["value"]) / peak, 1)
        hi, lo = out[0], out[-1]
        how = "Summing each country's latest value" if additive(ind) else "Weighting each country by its population"
        text = [f"{how}, {lc(ind['name'])} is {'largest' if additive(ind) else 'highest'} in {hi['g']['name']} ({hi['text']}) "
                f"and {'smallest' if additive(ind) else 'lowest'} in {lo['g']['name']} ({lo['text']})."]
        if not additive(ind) and lo["value"]:
            ratio = hi["value"] / lo["value"] if lo["value"] > 0 else None
            if ratio and ratio >= 1.5:
                text.append(f"That is {ratio:.1f} times as high.")
        return {"text": text, "regions": out, "big": hi["g"]["name"], "big_label": f"{'Largest' if additive(ind) else 'Highest'} region",
                "finding": f"By region, {lc(ind['name'])} is {'largest' if additive(ind) else 'highest'} in {hi['g']['name']} and "
                           f"{'smallest' if additive(ind) else 'lowest'} in {lo['g']['name']}.",
                "title": f"{ind['name']} by region"}

    def s_gap(self, ind: dict, s: dict):
        since = s.get("since", 2000)
        years = sorted({y for e in self.big for y, _, _ in self.m.series(e["entity_id"], ind["id"]) if y >= since})
        p10, p50, p90 = [], [], []
        for y in years:
            vals = sorted(v for e in self.big for yy, v, _ in self.m.series(e["entity_id"], ind["id"]) if yy == y)
            if len(vals) < 40:
                continue
            q = statistics.quantiles(vals, n=10)
            p10.append((y, q[0])); p50.append((y, statistics.median(vals))); p90.append((y, q[-1]))
        if len(p10) < 5:
            return None
        g0, g1 = p90[0][1] - p10[0][1], p90[-1][1] - p10[-1][1]
        y0, y1 = p10[0][0], p10[-1][0]
        trend = "narrowed" if abs(g1) < abs(g0) else "widened"
        gv = (lambda g: f"{abs(g):.1f} points") if ind["unit"].startswith("%") else (lambda g: self.v(abs(g), ind))
        text = [f"In {y0}, the country at the 90th percentile had {self.v(p90[0][1], ind)} and the one at the 10th "
                f"had {self.v(p10[0][1], ind)}: a gap of {gv(g0)}.",
                f"By {y1} the gap had {trend} to {gv(g1)}, with the typical country at {self.v(p50[-1][1], ind)}."]
        chart = svg.line_chart([{"label": "Top tenth (90th pct)", "points": p90, "cls": "s1"},
                                {"label": "Median", "points": p50, "cls": "s2"},
                                {"label": "Bottom tenth (10th pct)", "points": p10, "cls": "s3"}],
                               ind["unit"], decimals=ind.get("decimals", 1), title=f"Spread of {lc(ind['name'])}")
        return {"text": text, "chart": chart, "big": trend.capitalize(), "big_label": f"Gap between leaders and laggards, {y0}–{y1}",
                "finding": f"The gap in {lc(ind['name'])} between leading and lagging countries {trend} from "
                           f"{gv(g0)} to {gv(g1)} ({y0}–{y1}).",
                "title": f"Is the world converging on {lc(ind['name'])}?"}

    # ------------------------------------------------------------------ region reports
    REGION_INDS = ["gdp-per-capita-ppp", "life-expectancy", "under5-mortality", "fertility", "urban-share", "internet-users",
                   "electricity-access", "clean-electricity-share", "co2-per-capita", "unemployment"]

    def region_value(self, members: list[str], i: str):
        ind = self.ind(i)
        vals = [(x, lt) for x in members if (lt := self.m.latest(x, i, min_year=2015))]
        if len(vals) < 3:
            return None
        if additive(ind):
            return sum(lt[1] for _, lt in vals)
        w = [(self.pop.get(x, 0), lt[1]) for x, lt in vals if self.pop.get(x, 0) > 0]
        tot = sum(p for p, _ in w)
        return sum(p * v for p, v in w) / tot if tot else None

    def region_reports(self) -> list:
        out = []
        for g, members in self.regions.items():
            pool = [e for e in self.countries if e["entity_id"] in members and self.pop.get(e["entity_id"], 0) >= MIN_POP]
            if len(pool) < 4:
                continue
            region = self.by_id[g]
            table = []
            for i in self.REGION_INDS:
                if i not in self.m.indicators:
                    continue
                ind = self.ind(i)
                rv, w = self.region_value(members, i), self.m.latest("WLD", i)
                if rv is None or not w:
                    continue
                better = (rv > w[1]) == (ind["direction"] == "higher_better") if ind["direction"] != "neutral" else None
                table.append({"ind": ind, "region": self.v(rv, ind), "world": self.v(w[1], ind), "better": better})
            self.pool = pool
            secs = [x for x in (self.section({"kind": k, "indicator": i, **extra}) for k, i, extra in
                                (("leaders", "gdp-per-capita-ppp", {}), ("movers", "gdp-per-capita-ppp", {"years": 10}),
                                 ("leaders", "life-expectancy", {}), ("movers", "internet-users", {"years": 10}),
                                 ("leaders", "clean-electricity-share", {})) if i in self.m.indicators) if x]
            self.pool = None
            for x in secs:                                     # region-scoped wording
                x["title"] = x["title"].replace("Who leads in", "Who leads the region in").replace("Biggest movers in", "Biggest movers in the region:")
            ahead = [t for t in table if t["better"]]
            behind = [t for t in table if t["better"] is False]
            findings = []
            if ahead:
                findings.append(f"{region['name']} is ahead of the world average on {len(ahead)} of {len(ahead) + len(behind)} measures, including {lc(ahead[0]['ind']['name'])}.")
            if behind:
                findings.append(f"It is behind on {lc(behind[0]['ind']['name'])} ({behind[0]['region']} against {behind[0]['world']} worldwide).")
            findings += [x["finding"] for x in secs if x.get("finding")]
            out.append({"id": region["slug"], "g": region, "title": f"{region['name']}: regional report", "n": len(members),
                        "table": table, "sections": secs, "findings": findings, "kicker": "Region"})
        return out

    # ------------------------------------------------------------------ custom report builder data
    def builder_files(self, hubs: list[dict], out: Path) -> None:
        """One small JSON per country, plus a meta file, for the in-browser report builder."""
        out.mkdir(parents=True, exist_ok=True)
        ids = sorted({i for h in hubs for i in h["indicators"]})
        meta = {"inds": {}, "topics": [{"id": h["id"], "name": h["name"], "inds": h["indicators"]} for h in hubs]}
        ranks: dict[str, dict] = {}
        for i in ids:
            ind = self.ind(i)
            meta["inds"][i] = {"n": ind["name"], "u": ind["unit"], "d": ind.get("decimals", 1),
                               # totals mostly measure a country's size, so they are ranked largest-first, not good/bad
                               "dir": "neutral" if additive(ind) else ind["direction"],
                               "s": ind["source"], "add": additive(ind)}
            rows = self.latest_rows(i, pool=self.countries)
            rows.sort(key=lambda r: r[2], reverse=additive(ind) or self.best_first(ind))
            ranks[i] = {e["entity_id"]: (k + 1, len(rows)) for k, (e, _, _) in enumerate(rows)}
            w = self.m.latest("WLD", i)
            meta["inds"][i]["w"] = [w[0], round(w[1], 6)] if w else None
            meta["inds"][i]["ws"] = [[y, round(v, 4)] for y, v, _ in self.m.series("WLD", i) if y >= 2000]
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        region_of = {x: g for g, mem in self.regions.items() for x in mem}
        reg_cache: dict[tuple, float | None] = {}

        def region_value(g, i):
            if (g, i) not in reg_cache:
                ind = self.ind(i)
                vals = [(x, lt) for x in self.regions[g] if (lt := self.m.latest(x, i, min_year=2015))]
                if len(vals) < 3:
                    reg_cache[(g, i)] = None
                elif additive(ind):
                    reg_cache[(g, i)] = None            # a region's total is not comparable to one country
                else:
                    w = [(self.pop.get(x, 0), lt[1]) for x, lt in vals if self.pop.get(x, 0) > 0]
                    tot = sum(p for p, _ in w)
                    reg_cache[(g, i)] = sum(p * v for p, v in w) / tot if tot else None
            return reg_cache[(g, i)]

        for e in self.countries:
            eid = e["entity_id"]
            g = region_of.get(eid)
            d = {"id": eid, "name": e["name"], "slug": e["slug"], "region": self.by_id[g]["name"] if g else None, "ind": {}}
            for i in ids:
                lt = self.m.latest(eid, i, min_year=2010)
                if not lt:
                    continue
                base = self.at(eid, i, lt[0] - 10, slack=1)
                rk = ranks[i].get(eid)
                rv = region_value(g, i) if g else None
                spark = [[y, round(v, 4)] for y, v, _ in self.m.series(eid, i) if y >= 2000]
                d["ind"][i] = [lt[0], round(lt[1], 6), rk[0] if rk else None, rk[1] if rk else None,
                               base[0] if base else None, round(base[1], 6) if base else None,
                               round(rv, 6) if rv is not None else None, spark]
            (out / f"{eid}.json").write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
