"""Stage 3: render the static website from the Model into dist/."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import beyond, history, lab, live, og, stories, svg
from .build_data import Model
from .config import CONTENT, DIST, RAW, SITE, load_yaml, site_config

KIND_LABEL = {"official_reproduction": "Official", "original_composite": "Original index",
              "single_indicator": "Indicator ranking"}
EXCLUDED_LABEL = {
    "coverage_below_threshold": "Insufficient data", "ineligible_population": "Population under 500k",
    "not_in_hdr": "Not covered by UNDP", "no_recent_data": "No recent data",
}
SOURCE_SHORT = {"un-wpp": "UN WPP", "wb-wgi": "World Bank WGI", "wb-wdi": "World Bank", "undp-hdr": "UNDP HDR", "ti-cpi": "Transparency Intl",
                "oecd": "OECD", "gdelt": "GDELT"}
NE_FIX = {"KOS": "XKX", "SDS": "SSD", "PSX": "PSE", "SAH": "ESH", "JEY": "CHI", "GGY": "CHI"}  # WB reports the Channel Islands as one


def fmt(v, decimals: int = 2, unit: str = "") -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e6:
        s = svg.compact(v, 2 if abs(v) < 1e10 else 1)
    else:
        s = f"{v:,.{decimals}f}"
    if unit.startswith("current US$") and not unit.endswith("person"):
        s = "$" + s
    return s


def unit_short(unit: str) -> str:
    return {"current US$": "", "people": "", "applications": ""}.get(unit, unit)


class Site:
    def __init__(self, model: Model):
        self.m = model
        self.cfg = site_config()
        self.env = Environment(loader=FileSystemLoader(SITE / "templates"),
                               autoescape=select_autoescape(["html", "xml"]),
                               trim_blocks=True, lstrip_blocks=True)
        self.env.filters["fmt"] = fmt
        self.env.filters["unit_short"] = unit_short
        self.env.filters["compact"] = svg.compact
        self.env.filters["tojson_safe"] = lambda o: Markup(json.dumps(o, ensure_ascii=False).replace("<", "\\u003c"))
        self.env.globals.update(year_label=svg.year_label, SOURCE_SHORT=SOURCE_SHORT, site=self.cfg, release=model.release, KIND_LABEL=KIND_LABEL,
                                EXCLUDED_LABEL=EXCLUDED_LABEL, nav=self.nav())
        self.pages: list[str] = []
        self.search: list[dict] = []
        countries = model.countries()
        self.by_id = {e["entity_id"]: e for e in model.entities.values()}
        self.env.globals["ename"] = lambda e: self.by_id[e]["name"]
        flags = {p.stem for p in (SITE / "static" / "flags").glob("*.svg")}

        def flag(iso3: str, eager: bool = False) -> Markup:
            iso2 = (self.by_id.get(iso3, {}).get("iso2") or "").lower()
            if iso2 not in flags:
                return Markup("")
            load = "" if eager else ' loading="lazy"'      # above-the-fold flags load straight away
            return Markup(f'<img class="flag" src="/static/flags/{iso2}.svg" width="20" height="15" alt=""{load}>')

        self.env.globals["flag"] = flag
        self.env.globals["live"] = self.live_context()
        digest = hashlib.sha256()
        for f in sorted((SITE / "static").rglob("*")):
            if f.is_file():
                digest.update(f.read_bytes())
        self.env.globals["asset_v"] = digest.hexdigest()[:10]    # cache-busting for /static assets
        self.env.filters["ename_ind"] = lambda i: model.indicators[i]["name"]
        self.countries = countries
        self.dims = {d["id"]: d for d in model.dimensions}
        self.rk = model.rankings

    # -- helpers ------------------------------------------------------------
    def live_context(self) -> dict | None:
        b = live.baseline(self.m)
        if not b:
            return None
        # A fixed moment, so the build is reproducible; JavaScript replaces these on load.
        y, mo, d = (int(x) for x in self.m.release.split("-"))
        ms = datetime(y, mo, d, 12, tzinfo=timezone.utc).timestamp() * 1000
        return {"base": b, "at": live.estimate(b, ms)}

    def column_cells(self, r: dict, row: dict) -> list[dict]:
        """Extra columns for wide ranking tables."""
        cells = []
        for col in r.get("columns", []):
            if col["id"] == "pop_2050":
                v = next((x[1] for x in self.m.projections.get(row["entity_id"], []) if x[0] == 2050), None)
                cells.append({"v": v, "text": fmt(v, 0) if v is not None else "—", "year": None, "stale": False})
                continue
            if col["id"] == "world_share":
                world = self.m.latest("WLD", r["indicator"], max_year=row.get("year")) if row.get("year") else None
                v = 100 * row["score"] / world[1] if world and row["score"] is not None else None
                cells.append({"v": v, "text": f"{v:.1f}%" if v is not None else "—", "year": None, "stale": False})
                continue
            ind = self.m.indicators[col["id"]]
            lt = self.m.latest(row["entity_id"], col["id"], min_year=2015)
            if not lt:
                cells.append({"v": None, "text": "—", "year": None, "stale": False})
                continue
            text = fmt(lt[1], ind.get("decimals", 2), ind["unit"]) + ("%" if ind["unit"].startswith("%") else "")
            cells.append({"v": lt[1], "text": text, "year": lt[0], "stale": lt[0] < 2019})
        return cells

    def projection_chart(self, eid: str, name: str) -> str | None:
        """UN population estimates and medium-variant projections, 1950-2100."""
        ser = self.m.projections.get(eid)
        if not ser:
            return None
        past = [(y, v) for y, v in ser if y <= 2023]
        future = [(y, v) for y, v in ser if y >= 2023]
        return svg.line_chart([{"label": "UN estimate", "points": past, "cls": "s1"},
                               {"label": "UN projection (medium)", "points": future, "cls": "s2"}],
                              "people", decimals=1, title=f"Population of {name}, 1950 to 2100")

    def country_answers(self, eid: str) -> list[dict]:
        """Question tabs: average how the country compares on each question's measures."""
        out = []
        for q in self.questions:
            items, pcts, missing = [], [], []
            for ind_id in q["indicators"]:
                ind = self.m.indicators[ind_id]
                lt = self.m.latest(eid, ind_id)
                p = self.pct.get((eid, ind_id))
                if not lt or p is None:
                    missing.append(ind["name"])
                    continue
                pcts.append(p)
                items.append({"ind": ind, "value": lt[1], "pct": p, "chip": self.chip(ind_id, lt[0], lt[2])})
            avg = round(sum(pcts) / len(pcts)) if len(pcts) >= 2 else None
            verdict = None if avg is None else q["high"] if avg >= 67 else q["low"] if avg < 33 else q["mid"]
            out.append({"q": q, "items": items, "missing": missing, "avg": avg, "verdict": verdict})
        return out

    @staticmethod
    def nav():
        return [("World", "/world/"), ("Explore", "/explore/"), ("Rankings", "/rankings/"), ("Countries", "/countries/"),
                ("Compare", "/compare/"), ("Topics", "/topics/"), ("Index Builder", "/index-builder/"), ("Lab", "/lab/"),
                ("Data", "/data/"), ("Insights", "/insights/")]

    def render(self, url: str, template: str, sitemap: bool = True, **ctx) -> None:
        ctx.setdefault("og_image", "/og/default.png")
        html = self.env.get_template(template).render(url=url, **ctx)
        path = DIST / url.strip("/") / "index.html" if url.endswith("/") else DIST / url.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        if sitemap:
            self.pages.append(url)

    def ind(self, ind_id: str) -> dict:
        return self.m.indicators[ind_id]

    def src(self, ind_id: str) -> dict:
        return self.m.sources[self.ind(ind_id)["source"]]

    def chip(self, ind_id: str, year: int | None, status: str = "measured") -> dict:
        s = self.src(ind_id)
        short = SOURCE_SHORT.get(s["source_id"], s["publisher"])
        return {"src": short, "year": year, "status": status, "licence": s["licence"],
                "url": f"/data/sources/#{s['source_id']}"}

    def ranking_rows(self, r: dict) -> list[dict]:
        rows = []
        for row in r["results"]:
            e = self.by_id[row["entity_id"]]
            rows.append({**row, "name": e["name"], "slug": e["slug"], "iso3": e["entity_id"],
                         "region": e["region"], "income": e["income"], "cells": self.column_cells(r, row)})
        return rows

    def map_values(self, r: dict) -> dict:
        return {row["entity_id"]: row["score"] for row in r["results"] if row["score"] is not None}

    # -- pages --------------------------------------------------------------
    def build(self) -> None:
        # Pages are rebuilt from scratch so renamed URLs don't linger. v1/ and history/ are data outputs.
        for name in ("countries", "regions", "rankings", "compare", "topics", "data", "methodology",
                     "insights", "about", "explore", "world", "index-builder", "ask", "static", "og", "embed", "lab",
                     "universities", "cities"):
            if (DIST / name).exists():
                shutil.rmtree(DIST / name)
        shutil.copytree(SITE / "static", DIST / "static")
        self.geo()
        og.card(DIST / "og" / "default.png", self.cfg["name"], "Open data on 217 countries", self.cfg["tagline"],
                ["Every number shows its source, year and method."])
        self.hist = history.assemble(self.m.entities)
        self.load_beyond()
        self.home()
        self.explore()
        self.rankings()
        self.countries_pages()
        self.history_pages()
        self.world_page()
        self.regions()
        self.compare()
        self.topics()
        self.data_pages()
        self.methodology()
        self.builder()
        self.lab_pages()
        self.beyond_pages()
        self.insights()
        self.static_pages()
        self.render("/404.html", "404.html", sitemap=False)
        self.write_search()
        self.write_sitemap()

    def geo(self) -> None:
        src = RAW / "ne" / "countries_ind_simplified.geojson"   # India point-of-view boundaries
        gj = json.loads(src.read_text(encoding="utf-8"))
        known = {c["entity_id"] for c in self.countries}

        def rnd(coords):
            if isinstance(coords[0], (int, float)):
                return [round(coords[0], 2), round(coords[1], 2)]
            return [rnd(c) for c in coords]

        feats = []
        for f in gj["features"]:
            if not f.get("geometry"):     # tiny islands removed by simplification
                continue
            p = f["properties"]
            code = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
            code = NE_FIX.get(code, code)
            feats.append({"type": "Feature", "properties": {"iso3": code, "name": p.get("NAME"),
                                                            "known": code in known},
                          "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}})
        out = DIST / "geo" / "countries.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))

    def featured(self) -> list[dict]:
        cards = []
        for rid in self.cfg["featured_rankings"]:
            r = self.rk[rid]
            rows = [x for x in self.ranking_rows(r) if x["rank"]][:5]
            cards.append({"r": r, "rows": rows})
        return cards

    def home(self) -> None:
        cap = self.rk["capability-index"]
        pairs = [(self.by_id[a], self.by_id[b]) for a, b in self.cfg["curated_pairs"][:6]]
        self.render("/", "home.html", featured=self.featured(), map_values=self.map_values(cap),
                    map_label=cap["name"], pairs=pairs, countries=self.countries,
                    n_countries=len(self.countries), n_indicators=len(self.m.indicators),
                    n_rankings=len(self.rk), hdi_check=self.m.hdi_check)

    def explore(self) -> None:
        inds = sorted(self.m.indicators.values(), key=lambda i: (i["dimension"], i["name"]))
        self.render("/explore/", "explore.html", indicators=inds, dims=self.dims)

    def rankings(self) -> None:
        groups = {}
        for r in self.rk.values():
            groups.setdefault(r["kind"], []).append(r)
        self.render("/rankings/", "rankings_index.html", groups=groups,
                    order=["official_reproduction", "original_composite", "single_indicator"])
        regions = sorted({c["region"] for c in self.countries})
        incomes = ["High income", "Upper middle income", "Lower middle income", "Low income"]
        for r in self.rk.values():
            rows = self.ranking_rows(r)
            pillars = r["definition"].get("pillars", [])
            ind_meta = self.ind(r["indicator"]) if r.get("indicator") else None
            if r["kind"] == "official_reproduction":
                chip = self.chip(r.get("indicator") or r["definition"].get("indicator", "hdi"), r["definition"]["year"])
            elif ind_meta:
                chip = self.chip(ind_meta["id"], None)
            else:
                chip = None
            self.ranking_extras(r, rows)
            self.render(f"/rankings/{r['ranking_id']}/", "ranking.html", og_image=f"/og/rankings/{r['ranking_id']}.png", r=r, rows=rows, pillars=pillars,
                        ind=ind_meta, chip=chip, regions=regions, incomes=incomes,
                        map_values=self.map_values(r), hdi_check=self.m.hdi_check,
                        indicators=self.m.indicators)
            self.search.append({"t": r["name"], "u": f"/rankings/{r['ranking_id']}/", "k": "Ranking",
                                "s": KIND_LABEL[r["kind"]]})

    def ranking_extras(self, r: dict, rows: list[dict]) -> None:
        """Share card and embeddable top-10 chart for one ranking."""
        ranked = [x for x in rows if x["rank"]]
        dec = 1 if r["kind"] == "original_composite" else r["decimals"]
        text = lambda v: fmt(v, dec, r["unit"]) + ("%" if r["unit"].startswith("%") else "")
        og.card(DIST / "og" / "rankings" / f"{r['ranking_id']}.png", self.cfg["name"], KIND_LABEL[r["kind"]], r["name"],
                [f"{x['rank']}. {x['name']}  {text(x['score'])}" for x in ranked[:3]])
        top = ranked[:10]
        mx = max((abs(x["score"]) for x in top), default=1) or 1
        items = [{**x, "text": text(x["score"]), "bar": round(max(2, 100 * abs(x["score"]) / mx), 1)} for x in top]
        html = self.env.get_template("embed.html").render(r=r, rows=items)
        path = DIST / "embed" / "rankings" / r["ranking_id"] / "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    def country_dims(self, e: dict) -> list[dict]:
        out = []
        for d in self.m.dimensions:
            items = []
            for ind in self.m.indicators.values():
                if ind["dimension"] != d["id"]:
                    continue
                ser = self.m.series(e["entity_id"], ind["id"])
                if not ser:
                    continue
                y, v, s = ser[-1]
                pts = [(yy, vv) for yy, vv, _ in ser if yy >= 2000]
                items.append({"ind": ind, "value": v, "year": y, "status": s,
                              "spark": svg.sparkline(pts, label=ind["name"]),
                              "chip": self.chip(ind["id"], y, s), "stale": y < 2019,
                              "pct": self.pct.get((e["entity_id"], ind["id"]))})
            if items:
                out.append({"dim": d, "items": items})
        return out

    def positions(self, eid: str) -> list[dict]:
        out = []
        for r in self.rk.values():
            row = next(x for x in r["results"] if x["entity_id"] == eid)
            out.append({"r": r, "row": row})
        out.sort(key=lambda p: (p["row"]["rank"] is None,
                                ["official_reproduction", "original_composite", "single_indicator"].index(p["r"]["kind"])))
        return out

    def countries_pages(self) -> None:
        from .build_data import percentiles
        self.pct = percentiles(self.m)
        self.questions = load_yaml("country_questions.yaml")["questions"]
        by_region = {}
        for c in self.countries:
            by_region.setdefault(c["region"], []).append(c)
        self.render("/countries/", "countries_index.html", by_region=dict(sorted(by_region.items())),
                    countries=self.countries)
        cap = self.rk["capability-index"]
        cap_rows = {r["entity_id"]: r for r in cap["results"]}
        area_ranking = self.rk.get("surface-area")
        area_rows = {r["entity_id"]: r for r in area_ranking["results"]} if area_ranking else {}
        for c in self.countries:
            eid = c["entity_id"]
            key = {k: self.m.latest(eid, k) for k in ("population", "gdp", "gdp-per-capita-ppp", "hdi", "life-expectancy")}
            peers = [self.by_id[p] for p in self.m.groups.get(c["region_id"], []) if p != eid]
            pillar_names = {p["id"]: p["name"] for p in cap["definition"]["pillars"]}
            cr = cap_rows.get(eid)
            pb = svg.pillar_bars([(pillar_names[k], v) for k, v in cr["pillar_scores"].items()]) if cr and cr["rank"] else ""
            composites = []
            for comp in (r for r in self.rk.values() if r["kind"] == "original_composite"):
                row = next(x for x in comp["results"] if x["entity_id"] == eid)
                names = {p["id"]: p["name"] for p in comp["definition"]["pillars"]}
                bars = svg.pillar_bars([(names[k], v) for k, v in row["pillar_scores"].items()]) if row["rank"] else ""
                composites.append({"r": comp, "row": row, "bars": bars})
            hdi_ser = [(y, v) for y, v, _ in self.m.series(eid, "hdi")]
            gdp_ser = [(y, v) for y, v, _ in self.m.series(eid, "gdp-per-capita-ppp")]
            charts = []
            if hdi_ser:
                charts.append(("Human Development Index", svg.line_chart(
                    [{"label": c["name"], "points": hdi_ser}], "index", decimals=2, title=f"HDI of {c['name']}"),
                    self.chip("hdi", hdi_ser[-1][0])))
            if gdp_ser:
                charts.append(("GDP per capita, PPP (current international $)", svg.line_chart(
                    [{"label": c["name"], "points": gdp_ser}], "$", decimals=0, title=f"GDP per capita of {c['name']}"),
                    self.chip("gdp-per-capita-ppp", gdp_ser[-1][0])))
            proj = self.projection_chart(eid, c["name"])
            if proj:
                charts.append(("Population to 2100 (UN)", proj, self.chip("median-age", 2100, "forecast")))
            pair_links = [(self.by_id[a], self.by_id[b]) for a, b in self.cfg["curated_pairs"] if eid in (a, b)]
            lines = []
            if key.get("population"):
                lines.append(f"Population {fmt(key['population'][1], 0)} ({key['population'][0]})")
            if key.get("gdp-per-capita-ppp"):
                lines.append(f"GDP per person, PPP {fmt(key['gdp-per-capita-ppp'][1], 0)}")
            if key.get("hdi"):
                lines.append(f"Human Development Index {key['hdi'][1]:.3f}")
            og.card(DIST / "og" / "countries" / f"{c['slug']}.png", self.cfg["name"], c["region"], c["name"], lines)
            self.render(f"/countries/{c['slug']}/", "country.html", og_image=f"/og/countries/{c['slug']}.png", c=c, key=key, dims=self.country_dims(c),
                        positions=self.positions(eid), peers=peers, region=self.by_id[c["region_id"]],
                        income=self.by_id.get(c["income_id"]) if c["income_id"] else None,
                        cap=cap, cap_row=cr, pillar_bars=pb, composites=composites, charts=charts, pair_links=pair_links,
                        chips={k: self.chip(k, v[0], v[2]) for k, v in key.items() if v},
                        hist=self.hist[eid], chain=self.history_chain(eid), answers=self.country_answers(eid),
                        facts=self.m.facts.get(eid, {}), area=self.m.latest(eid, "surface-area"),
                        area_row=area_rows.get(eid), area_of=area_ranking["ranked_count"] if area_ranking else None)
            self.search.append({"t": c["name"], "u": f"/countries/{c['slug']}/", "k": "Country",
                                "s": c["region"], "a": c["entity_id"], "f": (c.get("iso2") or "").lower(),
                                "o": [x for x in [c["source_name"], *c.get("aliases", [])] if x != c["name"]]})

    @staticmethod
    def century(y: int) -> str:
        n = (y - 1) // 100 + 1 if y > 0 else (-y - 1) // 100 + 1
        suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suf} century" + (" BCE" if y < 0 else "")

    def history_chain(self, eid: str) -> list[str]:
        """Main succession for the country-page teaser: largest non-umbrella holders, in order."""
        rows = [p for p in self.hist[eid]["polities"] if not p["umbrella"] and p["peak"] >= 0.3]
        rows.sort(key=lambda p: (p["last"], p["first"]))      # so the present-day state comes last
        return [p["name"] for p in rows]

    def history_pages(self) -> None:
        for c in self.countries:
            eid = c["entity_id"]
            h = self.hist[eid]
            strip = svg.succession(h["polities"], h["range"][0], h["range"][1], h["events"]) if h["polities"] else ""
            groups, cur = [], None
            for e in h["events"]:
                name = self.century(e["start"])
                if name != cur:
                    groups.append((name, []))
                    cur = name
                groups[-1][1].append(e)
            longrun = []
            lr = h["longrun"]
            if len(lr["gdppc"]) >= 2:
                longrun.append(("GDP per capita (2011 int. $)", svg.line_chart(
                    [{"label": c["name"], "points": [tuple(p) for p in lr["gdppc"]]}], "$", decimals=0,
                    title=f"GDP per capita of {c['name']} over the long run", connect=True, log=True)))
            if len(lr["pop"]) >= 2:
                longrun.append(("Population", svg.line_chart(
                    [{"label": c["name"], "points": [tuple(p) for p in lr["pop"]]}], "people", decimals=1,
                    title=f"Population of {c['name']} over the long run", connect=True, log=True)))
            self.render(f"/countries/{c['slug']}/history/", "history.html", og_image=f"/og/countries/{c['slug']}.png", c=c, h=h, strip=strip,
                        events_by_century=groups, longrun=longrun, by_id=self.by_id)
            self.search.append({"t": f"{c['name']}: history", "u": f"/countries/{c['slug']}/history/",
                                "k": "History", "s": "200 BCE to today"})

    def world_page(self) -> None:
        labels = [("population", "Population"), ("gdp", "GDP (current US$)"), ("gdp-per-capita-ppp", "GDP per person, PPP"),
                  ("life-expectancy", "Life expectancy"), ("hdi", "Human Development Index"), ("internet-users", "Internet users"),
                  ("co2-per-capita", "CO₂ per person"), ("fertility", "Fertility rate"), ("urban-share", "Urban population")]
        key = []
        for ind_id, label in labels:
            lt = self.m.latest("WLD", ind_id)
            if lt:
                key.append({"ind": self.m.indicators[ind_id], "label": label, "value": lt[1], "chip": self.chip(ind_id, lt[0], lt[2])})
        wpop, wgdp = self.m.latest("WLD", "population"), self.m.latest("WLD", "gdp")
        regions = []
        for gid, members in self.m.groups.items():
            g = self.by_id[gid]
            if g["group_kind"] != "region":
                continue
            pop = sum((self.m.latest(x, "population") or (0, 0))[1] for x in members)
            gdp = sum((self.m.latest(x, "gdp") or (0, 0))[1] for x in members)
            regions.append({"g": g, "n": len(members), "people": pop, "gdp": gdp, "pop_share": 100 * pop / wpop[1],
                            "gdp_share": 100 * gdp / wgdp[1]})
        regions.sort(key=lambda r: -r["people"])
        charts = []
        for ind_id, title in (("population", "World population"), ("gdp-per-capita-ppp", "GDP per person, PPP"),
                              ("life-expectancy", "Life expectancy"), ("co2-per-capita", "CO₂ per person")):
            ind = self.m.indicators[ind_id]
            pts = [(y, v) for y, v, _ in self.m.series("WLD", ind_id)]
            if pts:
                charts.append((title, svg.line_chart([{"label": "World", "points": pts}], ind["unit"],
                                                     decimals=ind.get("decimals", 1), title=title)))
        proj = self.projection_chart("WLD", "the world")
        if proj:
            charts.append(("World population to 2100 (UN)", proj))
        wlines = [f"{x['label']} {fmt(x['value'], x['ind'].get('decimals', 1), x['ind']['unit'])}" for x in key[:3]]
        og.card(DIST / "og" / "world.png", self.cfg["name"], "Global totals", "The world in numbers", wlines)
        self.render("/world/", "world.html", og_image="/og/world.png", key=key, regions=regions, charts=charts, dims=self.country_dims(self.by_id["WLD"]))
        self.search.append({"t": "World", "u": "/world/", "k": "World", "s": "Global totals and live estimates",
                            "o": ["global", "world population", "earth"]})
        if self.env.globals["live"]:
            self.render("/methodology/live-estimates/", "live_method.html", b=self.env.globals["live"]["base"])

    def regions(self) -> None:
        for gid, members in self.m.groups.items():
            g = self.by_id[gid]
            rows = []
            for mid in sorted(members, key=lambda x: self.by_id[x]["name"]):
                e = self.by_id[mid]
                rows.append({"e": e, **{k: self.m.latest(mid, k) for k in
                                        ("population", "gdp-per-capita-ppp", "hdi", "life-expectancy")}})
            self.render(f"/regions/{g['slug']}/", "region.html", g=g, rows=rows,
                        map_values={r["e"]["entity_id"]: 1 for r in rows})
            self.search.append({"t": g["name"], "u": f"/regions/{g['slug']}/", "k": "Group",
                                "s": "Region" if g["group_kind"] == "region" else "Income group"})

    def compare_rows(self, ids: list[str]) -> list[dict]:
        out = []
        for d in self.m.dimensions:
            items = []
            for ind in self.m.indicators.values():
                if ind["dimension"] != d["id"]:
                    continue
                vals = [self.m.latest(e, ind["id"]) for e in ids]
                if not any(vals):
                    continue
                years = {v[0] for v in vals if v}
                items.append({"ind": ind, "vals": vals, "years_differ": len(years) > 1,
                              "chip": self.chip(ind["id"], None)})
            if items:
                out.append({"dim": d, "items": items})
        return out

    def compare(self) -> None:
        self.render("/compare/", "compare.html", countries=self.countries)
        for a, b in self.cfg["curated_pairs"]:
            ea, eb = sorted((self.by_id[a], self.by_id[b]), key=lambda e: e["slug"])
            ids = [ea["entity_id"], eb["entity_id"]]
            charts = []
            for ind_id in ("gdp-per-capita-ppp", "hdi", "life-expectancy", "internet-users"):
                series = [{"label": self.by_id[e]["name"], "points": [(y, v) for y, v, _ in self.m.series(e, ind_id)],
                           "cls": f"s{i+1}"} for i, e in enumerate(ids)]
                charts.append((self.ind(ind_id), svg.line_chart(series, self.ind(ind_id)["unit"],
                               decimals=self.ind(ind_id)["decimals"], title=self.ind(ind_id)["name"])))
            pos = [{p["r"]["ranking_id"]: p for p in self.positions(e)} for e in ids]
            self.render(f"/compare/{ea['slug']}-vs-{eb['slug']}/", "compare_pair.html", ents=[ea, eb],
                        rows=self.compare_rows(ids), charts=charts, pos=pos, rankings=self.rk)
            self.search.append({"t": f"{ea['name']} vs {eb['name']}", "u": f"/compare/{ea['slug']}-vs-{eb['slug']}/",
                                "k": "Compare", "s": "Side-by-side"})

    def topics(self) -> None:
        cards = []
        for d in self.m.dimensions:
            inds = [i for i in self.m.indicators.values() if i["dimension"] == d["id"]]
            rks = [r for r in self.rk.values() if d["id"] in r.get("topics", [])]
            cards.append({"d": d, "inds": inds, "rks": rks})
            self.render(f"/topics/{d['id']}/", "topic.html", d=d, inds=inds, rks=rks)
            self.search.append({"t": d["name"], "u": f"/topics/{d['id']}/", "k": "Topic", "s": d["blurb"]})
        self.render("/topics/", "topics_index.html", cards=cards)

    def data_pages(self) -> None:
        inds = list(self.m.indicators.values())
        self.render("/data/", "data_index.html", n_obs=sum(len(v) for v in self.m.obs.values()))
        self.render("/data/indicators/", "indicators_index.html", dims=self.m.dimensions, inds=inds,
                    sources=self.m.sources)
        countries = [c["entity_id"] for c in self.countries]
        used_in = {}
        for r in self.rk.values():
            for p in r["definition"].get("pillars", []):
                for i in p["indicators"]:
                    used_in.setdefault(i["id"], []).append(r)
            if r.get("indicator"):
                used_in.setdefault(r["indicator"], []).append(r)
        for comp in ("life-expectancy-hdr", "expected-schooling", "mean-schooling", "gni-per-capita"):
            used_in.setdefault(comp, []).append(self.rk["human-development-index"])
        for ind in inds:
            latest = []
            for e in countries:
                lt = self.m.latest(e, ind["id"])
                if lt:
                    latest.append({"e": self.by_id[e], "year": lt[0], "value": lt[1], "status": lt[2]})
            rev = ind["direction"] != "lower_better"
            latest.sort(key=lambda x: x["value"], reverse=rev)
            big = sorted(countries, key=lambda e: -((self.m.latest(e, "population") or (0, 0))[1]))[:6]
            series = [{"label": self.by_id[e]["name"], "points": [(y, v) for y, v, _ in self.m.series(e, ind["id"])],
                       "cls": f"s{i+1}"} for i, e in enumerate(big)]
            chart = svg.line_chart(series, ind["unit"], decimals=ind["decimals"], title=ind["name"])
            cov = {}
            for e in countries:
                for y, _, _ in self.m.series(e, ind["id"]):
                    cov[y] = cov.get(y, 0) + 1
            latest_year = max(cov) if cov else None
            recent = sum(1 for x in latest if x["year"] >= 2019)
            self.render(f"/data/indicators/{ind['id']}/", "indicator.html", ind=ind, src=self.src(ind["id"]),
                        latest=latest, chart=chart, cov=sorted(cov.items()), latest_year=latest_year,
                        n_countries=len(countries), recent=recent, used_in=used_in.get(ind["id"], []),
                        dim=self.dims[ind["dimension"]],
                        map_values={x["e"]["entity_id"]: x["value"] for x in latest},
                        lower_better=ind["direction"] == "lower_better")
            self.search.append({"t": ind["name"], "u": f"/data/indicators/{ind['id']}/", "k": "Indicator",
                                "s": self.dims[ind["dimension"]]["name"]})
        used = sorted({i["source"] for i in inds} | {"natural-earth", "wikidata", "cliopatria", "maddison", "ucdp"})
        excluded = [s for s in self.m.sources.values() if s["source_id"] not in used]
        self.render("/data/sources/", "sources.html", used=[self.m.sources[s] for s in used], excluded=excluded,
                    counts={s: sum(1 for i in inds if i["source"] == s) for s in used}, warnings=self.m.warnings)
        rel = DIST / "v1" / "releases" / self.m.release
        files = [{"name": p.name, "bytes": p.stat().st_size} for p in sorted((rel / "bulk").iterdir())]
        self.render("/data/downloads/", "downloads.html", files=files)
        self.render("/data/api/", "api.html", sample_country=self.countries[0] if self.countries else None)

    def methodology(self) -> None:
        self.render("/methodology/", "methodology_index.html", rankings=self.rk)
        for r in self.rk.values():
            md_path = CONTENT / "methodology" / f"{r['ranking_id']}.md"
            body = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables"]) if md_path.exists() else ""
            self.render(f"/methodology/{r['ranking_id']}/", "methodology.html", r=r, body=body,
                        indicators=self.m.indicators, hdi_check=self.m.hdi_check, by_id=self.by_id,
                        sources=self.m.sources)

    def builder(self) -> None:
        cap = self.rk["capability-index"]
        comps = [r for r in self.rk.values() if r["kind"] == "original_composite"]
        self.render("/index-builder/", "builder.html", cap=cap, dims=self.m.dimensions, composites=comps)

    def load_beyond(self) -> None:
        """Universities and cities, grouped by country for the country pages."""
        self.unis = beyond.load_universities(self.m)
        for u in self.unis:
            u["country_label"] = {"TW": "Taiwan"}.get(u.get("cc") or "", "") if not u["iso3"] else ""
        self.cities, unmatched = beyond.load_cities(self.m)
        if unmatched:
            print(f"  cities: no country match for {', '.join(unmatched)}")
        by_c: dict[str, dict] = {}
        for u in self.unis:
            if u["iso3"]:
                by_c.setdefault(u["iso3"], {"unis": [], "cities": []})["unis"].append(u)
        for c in self.cities:
            if c["iso3"]:
                by_c.setdefault(c["iso3"], {"unis": [], "cities": []})["cities"].append(c)
        self.env.globals["beyond"] = by_c
        self.env.globals["beyond_counts"] = {"unis": len(self.unis), "cities": len(self.cities)}

    def beyond_pages(self) -> None:
        def countries_of(items):
            isos = {x["iso3"] for x in items if x["iso3"]}
            opts = sorted(((i, self.by_id[i]["name"]) for i in isos), key=lambda t: t[1])
            extra = sorted({x.get("country_label") or x.get("country") for x in items if not x["iso3"]} - {None, ""})
            return opts + [(n, n) for n in extra]

        for u in self.unis:
            u.setdefault("country_label", "")
        if self.unis:
            meta = json.loads((RAW / "openalex" / "institutions.json.meta.json").read_text(encoding="utf-8"))
            self.render("/universities/", "universities.html", unis=self.unis, countries=countries_of(self.unis),
                        by_id=self.by_id, retrieved=meta.get("retrieved_at", "")[:10])
            self.search.append({"t": "Universities by research citations", "u": "/universities/", "k": "List", "s": "OpenAlex"})
        if self.cities:
            self.render("/cities/", "cities.html", cities=self.cities, countries=countries_of(self.cities), by_id=self.by_id)
            self.search.append({"t": "The world's largest cities", "u": "/cities/", "k": "List", "s": "GHSL urban centres"})
            for c in self.cities[:300]:
                if c["iso3"]:
                    self.search.append({"t": c["name"], "u": f"/cities/#{c['iso3']}", "k": "City",
                                        "s": f"{self.by_id[c['iso3']]['name']} · {fmt(c['people'], 0)} people"})
        out = DIST / "data"
        out.mkdir(parents=True, exist_ok=True)
        (out / "universities.json").write_text(json.dumps({"source": "OpenAlex, CC0", "results": self.unis}, ensure_ascii=False,
                                                          separators=(",", ":")), encoding="utf-8")
        (out / "cities.json").write_text(json.dumps({"source": "GHS Urban Centre Database R2024A v1.2, European Commission JRC, CC BY 4.0",
                                                     "results": self.cities}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    BULK_ABOUT = {
        "observations": "Every value: one row per country (or group), indicator and year, with status, source and licence.",
        "entities": "Countries and groups: names, slugs, ISO codes, region, income group, capital.",
        "indicators": "Indicator definitions: name, unit, direction, topic, source and licence.",
        "ranking_results": "Every ranking's results: rank, ties, score, rank range and coverage.",
        "sources": "Sources and their licences.",
    }
    FIELD_ABOUT = {
        "entity_id": "ISO 3166 alpha-3 code (WLD = world, other groups have their own ids)", "indicator_id": "Indicator id (see the list below)",
        "year": "Year the value describes", "value": "The value, in the indicator's unit", "status": "measured, estimate or forecast",
        "source": "Source id", "source_licence": "Licence of this value", "source_url": "Where it was downloaded",
        "retrieved_at": "When it was downloaded (UTC)", "modified": "True if this site changed the value (e.g. unit conversion)",
        "type": "country or a group kind", "slug": "URL name on this site", "name": "Display name", "iso3": "ISO alpha-3",
        "region": "World Bank region", "income": "World Bank income group", "capital": "Capital city",
        "definition": "What it measures", "unit": "Unit", "direction": "higher_better, lower_better or neutral",
        "dimension": "Topic", "applies_to": "Entity types it applies to", "source_code": "The source's own series code",
        "display_only": "Shown for reference; not used in calculations", "decimals": "Decimals shown on the site",
        "transform": "log if composites use its logarithm", "ranking_id": "Ranking id", "version": "Methodology version",
        "rank": "Rank (1 = top)", "is_tied": "Shares its rank", "score": "Score or value", "rank_low": "Best rank in the sensitivity test",
        "rank_high": "Worst rank in the sensitivity test", "coverage": "Share of the ranking's indicators available",
        "excluded_reason": "Why a country is not ranked",
    }

    def lab_pages(self) -> None:
        import duckdb
        res = lab.Lab(self).build()
        f = res["findings"]
        inds = sorted(({"id": i["id"], "name": i["name"], "dimension": i["dimension"], "unit": i["unit"], "source": i["source"]}
                       for i in self.m.indicators.values()
                       if i["source"] != "gdelt" and not self.m.sources.get(i["source"], {}).get("no_modification")),
                      key=lambda i: i["name"].casefold())
        n_countries = len(self.countries)
        self.render("/lab/", "lab.html", f=f, n_inds=len(res["corr"]["ids"]), n_countries=n_countries)
        self.render("/lab/scatter/", "lab_scatter.html", inds=inds, dims=self.dims, n_countries=n_countries)
        self.render("/lab/correlations/", "lab_corr.html", inds=inds, dims=self.dims, method=res["corr"]["method"])
        self.render("/lab/findings/", "lab_findings.html", f=f)
        bulk = DIST / "v1" / "latest" / "bulk"
        files, schemas = [], []
        for name, about in self.BULK_ABOUT.items():
            for ext in ("parquet", "csv.gz"):
                p = bulk / f"{name}.{ext}"
                if p.exists():
                    kb = p.stat().st_size / 1024
                    files.append({"name": f"{name}.{ext}", "url": f"/v1/latest/bulk/{name}.{ext}", "about": about,
                                  "size": f"{kb / 1024:.1f} MB" if kb > 1024 else f"{kb:.0f} KB"})
            p = bulk / f"{name}.parquet"
            if p.exists():
                cols = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()
                schemas.append({"name": name, "cols": [{"name": c[0], "type": c[1].lower(), "about": self.FIELD_ABOUT.get(c[0], "")}
                                                       for c in cols]})
        self.render("/lab/data/", "lab_data.html", files=files, schemas=schemas, inds=inds,
                    base=self.cfg["base_url"].rstrip("/"))
        for url, t, s in (("/lab/", "The Lab", "Explore the data yourself"), ("/lab/scatter/", "Scatter explorer", "Plot any two indicators"),
                          ("/lab/correlations/", "Correlation atlas", "How indicators move together"),
                          ("/lab/findings/", "Findings", "What stood out in this release"),
                          ("/lab/data/", "Use the data", "Python, R and SQL starters")):
            self.search.append({"t": t, "u": url, "k": "Lab", "s": s})

    def insights(self) -> None:
        rel = {
            "n_obs": sum(len(v) for v in self.m.obs.values()), "n_rejects": len(self.m.rejects),
            "rejects_by_rule": {}, "source_releases": sorted(self.m.source_releases.values(),
                                                             key=lambda r: r["source_release_id"]),
        }
        for rj in self.m.rejects:
            rel["rejects_by_rule"][rj["rule"]] = rel["rejects_by_rule"].get(rj["rule"], 0) + 1
        self.stories = stories.build(self)
        for s in self.stories:
            self.render(f"/insights/{s['slug']}/", "story.html", sitemap=s["status"] == "published", s=s)
            if s["status"] == "published":
                self.search.append({"t": s["title"], "u": f"/insights/{s['slug']}/", "k": "Story", "s": s["dek"][:60]})
        self.render("/insights/", "insights.html", stories=self.stories)
        self.render(f"/insights/releases/{self.m.release}/", "release_notes.html", rel=rel,
                    rankings=self.rk, hdi_check=self.m.hdi_check, warnings=self.m.warnings,
                    rejects=self.m.rejects[:50], by_id=self.by_id)

    def static_pages(self) -> None:
        pages = {"about": "About", "editorial-policy": "Editorial policy", "errata": "Errata",
                 "licences": "Licences & how to cite", "funding": "Funding", "privacy": "Privacy"}
        for slug, title in pages.items():
            md = (CONTENT / "pages" / f"{slug}.md").read_text(encoding="utf-8")
            md = md.replace("{{ site.name }}", self.cfg["name"]).replace("{{ site.contact_email }}", self.cfg["contact_email"]) \
                   .replace("{{ release }}", self.m.release)
            body = markdown.markdown(md, extensions=["tables"])
            url = "/about/" if slug == "about" else f"/about/{slug}/"
            self.render(url, "page.html", title=title, body=body, about_nav=pages)
        self.render("/ask/", "ask.html")

    def write_search(self) -> None:
        (DIST / "search-index.json").write_text(json.dumps(self.search, ensure_ascii=False, separators=(",", ":")),
                                                encoding="utf-8")

    def write_sitemap(self) -> None:
        base = self.cfg["base_url"].rstrip("/")
        urls = "".join(f"<url><loc>{base}{u}</loc></url>" for u in sorted(set(self.pages)))
        (DIST / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>',
            encoding="utf-8")
        (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /index-builder/\n\nSitemap: {base}/sitemap.xml\n")
        repo = self.cfg.get("repo_url", "").rstrip("/")
        if repo.startswith("https://github.com/"):
            # Releases are archived on GitHub by the deploy workflow; send release links there so they never break.
            dl = f"{repo}/releases/download/data-:date"
            (DIST / "_redirects").write_text(f"/v1/releases/:date/bulk/:file {dl}/:file 302\n"
                                             f"/v1/releases/:date/:file {dl}/:file 302\n")
        (DIST / "_headers").write_text(
            "/v1/releases/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=31536000, immutable\n"
            "/v1/latest/*\n  Access-Control-Allow-Origin: *\n  Cache-Control: public, max-age=3600\n"
            "/static/*\n  Cache-Control: public, max-age=86400\n")


def build(model: Model) -> None:
    Site(model).build()
    n = sum(1 for p in DIST.rglob("*.html"))
    print(f"  {n} HTML pages written to dist/")
