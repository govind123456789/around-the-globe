"""Stand-out features: time twins, years to target, how well we know each country, the
"Where would I fit?" data and the animated timeline map.

Time twins compare a country's latest development profile with every other country's past, on
five standardised measures, and report the closest country-years. Years to target extend the
last ten years' straight-line trend; they describe the current pace, not a forecast.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

TWIN_INDS = [("gdp-per-capita-ppp", True), ("life-expectancy", False), ("fertility", False),
             ("urban-share", False), ("under5-mortality", True)]          # (indicator, log scale)
TARGETS = [("electricity-access", 100, "Everyone has electricity"), ("basic-water", 100, "Everyone has basic drinking water"),
           ("basic-sanitation", 100, "Everyone has basic sanitation"), ("clean-cooking", 100, "Everyone cooks with clean fuels"),
           ("internet-users", 90, "Nine in ten people online"), ("life-expectancy", 80, "Life expectancy of 80"),
           ("under5-mortality", 25, "Under-5 deaths below 25 per 1,000 (UN goal)")]
FIT = [("income", "Income", "gdp-per-capita-ppp", "higher_better", True), ("health", "Long lives", "life-expectancy", "higher_better", False),
       ("safety", "Personal safety", "homicide-rate", "lower_better", True), ("air", "Clean air", "pm25", "lower_better", False),
       ("honesty", "Low corruption", "cpi", "higher_better", False), ("voice", "Political freedom", "wgi-voice-accountability", "higher_better", False),
       ("stability", "Political stability", "wgi-political-stability", "higher_better", False), ("jobs", "Low unemployment", "unemployment", "lower_better", False),
       ("online", "Internet access", "internet-users", "higher_better", False), ("education", "University education", "tertiary-enrolment", "higher_better", False),
       ("green", "Clean electricity", "clean-electricity-share", "higher_better", False), ("prices", "Low inflation", "inflation", "lower_better", True)]
TIMELINE = ["life-expectancy", "gdp-per-capita-ppp", "internet-users", "fertility", "urban-share", "electricity-access",
            "under5-mortality", "co2-per-capita", "clean-electricity-share", "vdem-liberal-democracy", "aged-65", "women-parliament"]


def _ols_slope(pts):
    n = len(pts)
    mx = sum(x for x, _ in pts) / n
    my = sum(y for _, y in pts) / n
    den = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / den if den else 0.0


class Standout:
    def __init__(self, model, countries: list[dict], by_id: dict):
        self.m, self.countries, self.by_id = model, countries, by_id
        self.ids = [e["entity_id"] for e in countries]
        self.pop = {i: (model.latest(i, "population") or (0, 0, ""))[1] for i in self.ids}
        self.twins = self.compute_twins()
        self.targets = self.compute_targets()
        self.coverage = self.compute_coverage()

    # ------------------------------------------------------------------ time twins
    def compute_twins(self) -> dict:
        inds = [(i, lg) for i, lg in TWIN_INDS if i in self.m.indicators]
        rows = {}                                          # (iso, year) -> vector
        for iso in self.ids:
            series = [{y: v for y, v, _ in self.m.series(iso, i)} for i, _ in inds]
            years = set(series[0]).intersection(*series[1:]) if series else set()
            for y in years:
                vec = []
                for (i, lg), s in zip(inds, series):
                    v = s[y]
                    vec.append(math.log10(v) if lg and v > 0 else (v if not lg else None))
                if None not in vec:
                    rows[(iso, y)] = vec
        if not rows:
            return {}
        k = len(inds)
        sd = [statistics.pstdev(v[j] for v in rows.values()) or 1 for j in range(k)]
        by_iso = defaultdict(list)
        for (iso, y), v in rows.items():
            by_iso[iso].append((y, v))
        out = {}
        for iso in self.ids:
            mine = sorted(by_iso.get(iso, []))
            if not mine or mine[-1][0] < 2018 or self.pop.get(iso, 0) < 1e6:
                continue
            y0, v0 = mine[-1]
            best = []
            for other, lst in by_iso.items():
                if other == iso or self.pop.get(other, 0) < 1e6:
                    continue
                cand = [(math.sqrt(sum(((a - b) / s) ** 2 for a, b, s in zip(v0, v, sd))), y) for y, v in lst if y <= y0 - 8]
                if cand:
                    d, y = min(cand)
                    best.append((d, other, y))
            best.sort()
            out[iso] = {"year": y0, "twins": [{"e": self.by_id[o], "year": y, "dist": round(d, 2)} for d, o, y in best[:3]]}
        return out

    # ------------------------------------------------------------------ years to target
    def compute_targets(self) -> dict:
        out = defaultdict(list)
        for ind_id, target, label in TARGETS:
            if ind_id not in self.m.indicators:
                continue
            lower = self.m.indicators[ind_id]["direction"] == "lower_better"
            for iso in self.ids:
                ser = [(y, v) for y, v, _ in self.m.series(iso, ind_id)]
                if not ser or ser[-1][0] < 2018:
                    continue
                y1, v1 = ser[-1]
                done = v1 <= target if lower else v1 >= target
                status, year = None, None
                if done:
                    status = "achieved"
                else:
                    pts = [(y, v) for y, v in ser if y >= y1 - 10]
                    if len(pts) >= 6:
                        slope = _ols_slope(pts)
                        good = slope < 0 if lower else slope > 0
                        if good and abs(slope) > 1e-9:
                            year = y1 + (target - v1) / slope
                            status = "on track" if year <= 2030 else "too slow" if year <= 2100 else "stalled"
                        else:
                            status = "going backwards" if abs(slope) > 1e-9 else "stalled"
                if status:
                    out[iso].append({"ind": self.m.indicators[ind_id], "target": target, "label": label, "value": v1,
                                     "vyear": y1, "status": status, "year": math.ceil(year) if year else None})
        return out

    def target_tables(self) -> list:
        tables = []
        for ind_id, target, label in TARGETS:
            rows = [(self.by_id[i], t) for i, lst in self.targets.items() for t in lst if t["ind"]["id"] == ind_id]
            if not rows:
                continue
            tables.append({"label": label, "ind": rows[0][1]["ind"], "target": target,
                           "achieved": sum(1 for _, t in rows if t["status"] == "achieved"),
                           "on_track": sorted((r for r in rows if r[1]["status"] == "on track"), key=lambda r: r[1]["year"]),
                           "slow": sorted((r for r in rows if r[1]["status"] == "too slow"), key=lambda r: r[1]["year"]),
                           "off": [r for r in rows if r[1]["status"] in ("going backwards", "stalled")]})
        return tables

    # ------------------------------------------------------------------ how well do we know this country?
    def compute_coverage(self) -> dict:
        inds = [i for i in self.m.indicators.values() if i["source"] not in ("gdelt",)]
        out = {}
        for iso in self.ids:
            recent = ages = n = 0
            age_list = []
            for ind in inds:
                lt = self.m.latest(iso, ind["id"])
                if lt:
                    n += 1
                    age_list.append(max(0, 2025 - lt[0]))
                    if lt[0] >= 2019:
                        recent += 1
            share = recent / len(inds)
            med_age = statistics.median(age_list) if age_list else None
            score = 100 * share * (1 / (1 + (med_age or 10) / 10))
            out[iso] = {"recent": recent, "any": n, "total": len(inds), "share": 100 * share, "median_age": med_age}
        ranked = sorted(out, key=lambda i: (-out[i]["share"], out[i]["median_age"] or 99))
        for k, i in enumerate(ranked):
            out[i]["rank"] = k + 1
            out[i]["of"] = len(ranked)
        return out

    # ------------------------------------------------------------------ files for the browser tools
    def fit_data(self, risk_by: dict) -> dict:
        facs = [f for f in FIT if f[2] in self.m.indicators]
        data = {}
        cols = {}
        for key, label, ind, direction, lg in facs:
            vals = {i: lt[1] for i in self.ids if self.pop.get(i, 0) >= 1e6 and (lt := self.m.latest(i, ind, min_year=2015))}
            order = sorted(vals, key=lambda i: vals[i], reverse=direction == "higher_better")
            n = len(order)
            cols[key] = {i: round(1 - k / (n - 1), 3) for k, i in enumerate(order)} if n > 1 else {}
        peace = sorted((i for i in risk_by if self.pop.get(i, 0) >= 1e6), key=lambda i: risk_by[i]["score"])
        cols["peace"] = {i: round(1 - k / (len(peace) - 1), 3) for k, i in enumerate(peace)} if len(peace) > 1 else {}
        factors = [{"key": k, "label": l, "ind": i} for k, l, i, _, _ in facs] + [{"key": "peace", "label": "Low conflict risk", "ind": None}]
        for i in self.ids:
            if self.pop.get(i, 0) < 1e6:
                continue
            row = {f["key"]: cols[f["key"]].get(i) for f in factors}
            if sum(v is not None for v in row.values()) >= len(factors) - 3:
                data[i] = {"n": self.by_id[i]["name"], "s": self.by_id[i]["slug"], "v": row}
        return {"factors": factors, "countries": data}

    def timeline_files(self, out: Path, risk_hist: dict) -> list:
        out.mkdir(parents=True, exist_ok=True)
        listed = []
        for ind_id in TIMELINE:
            if ind_id not in self.m.indicators:
                continue
            ind = self.m.indicators[ind_id]
            d = {i: [[y, round(v, 4)] for y, v, _ in self.m.series(i, ind_id) if y >= 1990] for i in self.ids}
            d = {k: v for k, v in d.items() if v}
            allv = sorted(v for s in d.values() for _, v in s)
            if not allv:
                continue
            breaks = [allv[int(len(allv) * q / 7)] for q in range(1, 7)]
            (out / f"{ind_id}.json").write_text(json.dumps({"name": ind["name"], "unit": ind["unit"], "lower_better": ind["direction"] == "lower_better",
                                                            "breaks": breaks, "data": d}, separators=(",", ":")), encoding="utf-8")
            listed.append({"id": ind_id, "name": ind["name"]})
        if risk_hist:
            allv = sorted(v for s in risk_hist.values() for _, v in s)
            breaks = [allv[int(len(allv) * q / 7)] for q in range(1, 7)]
            (out / "risk.json").write_text(json.dumps({"name": "Geopolitical risk index", "unit": "0–100", "lower_better": True,
                                                       "breaks": breaks, "data": risk_hist}, separators=(",", ":")), encoding="utf-8")
            listed.insert(0, {"id": "risk", "name": "Geopolitical risk index"})
        return listed
