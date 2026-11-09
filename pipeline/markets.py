"""Markets: industry hubs (data/markets.yaml) built from the release's own indicators.

Each hub has a headline indicator that sizes the market. When the headline adds up across
countries (money, tonnes, TWh, people), a country's share of the world uses the source's own
world figure for the same year (World Bank or Ember), never a sum of whichever countries report.
"""
from __future__ import annotations

import csv
from pathlib import Path

from . import svg
from .config import load_yaml

STALE_YEARS = 4        # a country's value is shown if it is at most this many years older than the world's latest
LEADER_MIN_POP = 1e6   # "highest" columns skip micro-states, whose ratios are often extreme
GROWTH_POOL = 40       # fastest-growing list: only the 40 largest markets, so tiny bases don't dominate
UNIT_SUFFIX = {"tonnes": " t", "TWh": " TWh", "GW": " GW", "TEU": " TEU", "million tonne-km": " m t-km",
               "MtCO₂e": " Mt", "gCO₂e per kWh": " g/kWh"}


def cagr(v0: float, v1: float, years: int) -> float | None:
    if v0 and v1 and v0 > 0 and v1 > 0 and years > 0:
        return 100 * ((v1 / v0) ** (1 / years) - 1)
    return None


def share_text(s: float | None) -> str:
    if s is None:
        return "—"
    return "<0.1%" if s < 0.1 else f"{s:.1f}%"


class Markets:
    def __init__(self, model, countries: list[dict], rankings: dict, fmt):
        self.m, self.countries, self.rk, self._fmt = model, countries, rankings, fmt
        self.pop = {e["entity_id"]: (model.latest(e["entity_id"], "population") or (0, 0, ""))[1] for e in countries}
        self.hubs = []
        for h in load_yaml("markets.yaml")["markets"]:
            if h["headline"] not in model.indicators:
                continue                                   # its source was excluded from this release
            inds = [i for i in h["indicators"] if i in model.indicators]
            self.hubs.append(self.compute({**h, "indicators": inds}))
        self.by_hub = {h["id"]: h for h in self.hubs}

    # ------------------------------------------------------------------ formatting
    def show(self, v: float | None, ind: dict) -> str:
        if v is None:
            return "—"
        unit = ind["unit"]
        s = self._fmt(v, ind.get("decimals", 1), unit)
        if unit.startswith("%"):
            return s + "%"
        return s + UNIT_SUFFIX.get(unit, "")

    # ------------------------------------------------------------------ one hub
    def compute(self, h: dict) -> dict:
        m = self.m
        hl = m.indicators[h["headline"]]
        world = [(y, v) for y, v, _ in m.series("WLD", hl["id"])]
        wl = world[-1] if world else None
        min_year = (wl[0] - STALE_YEARS) if wl else 2015
        rows = []
        for e in self.countries:
            lt = m.latest(e["entity_id"], hl["id"], min_year=min_year)
            if lt:
                rows.append({"e": e, "year": lt[0], "value": lt[1], "status": lt[2]})
        rows.sort(key=lambda r: r["value"], reverse=hl["direction"] != "lower_better")
        if not h["additive"]:                              # ratios: rank countries of at least a million people
            rows = [r for r in rows if self.pop.get(r["e"]["entity_id"], 0) >= LEADER_MIN_POP]
        for i, r in enumerate(rows):
            r["rank"] = i + 1
            r["text"] = self.show(r["value"], hl)
            r["share"] = None
            if h["additive"]:
                w = m.latest("WLD", hl["id"], max_year=r["year"])
                if w and w[0] == r["year"] and w[1] > 0:
                    r["share"] = 100 * r["value"] / w[1]
            r["share_text"] = share_text(r["share"])
        top = rows[:15]
        peak = max((abs(r["value"]) for r in top), default=0) or 1
        for r in top:
            r["bar"] = round(100 * abs(r["value"]) / peak, 1)

        growth = None
        if wl:
            past = next(((y, v) for y, v in world if y >= wl[0] - 10), None)
            if past and past[0] < wl[0]:
                growth = {"rate": cagr(past[1], wl[1], wl[0] - past[0]), "from": past[0], "to": wl[0]}
        fastest = []
        if h["additive"]:
            for r in rows[:GROWTH_POOL]:
                ser = {y: v for y, v, _ in m.series(r["e"]["entity_id"], hl["id"])}
                g = cagr(ser.get(r["year"] - 5), r["value"], 5)
                if g is not None:
                    fastest.append({**r, "growth": g})
            fastest.sort(key=lambda r: -r["growth"])
            fastest = fastest[:8]
        top5 = [r["share"] for r in rows[:5]]
        top5_share = sum(top5) if len(top5) == 5 and all(s is not None for s in top5) else None

        table = []
        for ind_id in h["indicators"]:
            ind = m.indicators[ind_id]
            w = m.latest("WLD", ind_id)
            cands = []
            for e in self.countries:
                lt = m.latest(e["entity_id"], ind_id, min_year=2019)
                if lt and self.pop.get(e["entity_id"], 0) >= LEADER_MIN_POP:
                    cands.append((e, lt))
            leader = None
            if cands:
                pick = min if ind["direction"] == "lower_better" else max
                e, lt = pick(cands, key=lambda c: c[1][1])
                leader = {"e": e, "text": self.show(lt[1], ind), "year": lt[0], "v": lt[1]}
            covered = sum(1 for e in self.countries if m.latest(e["entity_id"], ind_id, min_year=2015))
            wpts = [(y, v) for y, v, _ in m.series("WLD", ind_id) if y >= 2000]
            table.append({"ind": ind, "world": self.show(w[1], ind) if w else None, "world_v": w[1] if w else None,
                          "world_year": w[0] if w else None, "leader": leader, "covered": covered,
                          "spark": svg.sparkline(wpts, label=f"World {ind['name']}") if len(wpts) > 1 else ""})

        if world:
            chart = svg.line_chart([{"label": "World", "points": world}], hl["unit"], decimals=hl.get("decimals", 1),
                                   title=f"{hl['name']}, world")
        else:
            series = [{"label": r["e"]["name"], "points": [(y, v) for y, v, _ in m.series(r["e"]["entity_id"], hl["id"])],
                       "cls": f"s{i + 1}"} for i, r in enumerate(rows[:5])]
            chart = svg.line_chart(series, hl["unit"], decimals=hl.get("decimals", 1), title=hl["name"])
        spark = svg.sparkline([(y, v) for y, v in world if y >= 2000], label=f"World {hl['name']}") if world else ""
        sources = sorted({m.indicators[i]["source"] for i in h["indicators"]})
        return {**h, "hl": hl, "world": wl, "world_text": self.show(wl[1], hl) if wl else None, "rows": rows,
                "top": top, "growth": growth, "fastest": fastest, "top5_share": top5_share, "table": table,
                "chart": chart, "spark": spark, "sources": sources,
                "map_values": {r["e"]["entity_id"]: r["value"] for r in rows},
                "rankings_list": [self.rk[r] for r in h.get("rankings", []) if r in self.rk],
                "n_countries": len(rows)}

    # ------------------------------------------------------------------ country view
    def country_shares(self, eid: str) -> list[dict]:
        out = []
        for h in self.hubs:
            if not h["additive"]:
                continue
            r = next((x for x in h["rows"] if x["e"]["entity_id"] == eid), None)
            if r and r["share"] is not None:
                out.append({"hub": h, "rank": r["rank"], "n": len(h["rows"]), "text": r["text"], "year": r["year"],
                            "share": r["share"], "share_text": r["share_text"]})
        return out

    # ------------------------------------------------------------------ downloads
    def write_csv(self, h: dict, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["iso3", "country"] + [x for i in h["indicators"] for x in (i, f"{i}_year")])
            for e in self.countries:
                row = [e["entity_id"], e["name"]]
                for i in h["indicators"]:
                    lt = self.m.latest(e["entity_id"], i, min_year=2010)
                    row += [lt[1], lt[0]] if lt else ["", ""]
                w.writerow(row)
