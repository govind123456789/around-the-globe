"""Geopolitics: organised violence (UCDP), UN General Assembly alignment (Voeten et al.),
displacement (UNHCR), an original transparent risk index, relations between pairs of countries
and a weekly briefing. Every figure here comes from a named, citable dataset; live news headlines
are added in the browser from GDELT and are labelled as unverified third-party reporting.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

from . import svg
from .config import RAW, load_yaml

TYPES = {1: "State-based conflict", 2: "Non-state conflict", 3: "One-sided violence"}
POWERS = ["USA", "CHN", "RUS", "IND", "FRA"]
POWER_NAMES = {"USA": "United States", "CHN": "China", "RUS": "Russia", "IND": "India", "FRA": "France"}
RISK_WEIGHTS = [("conflict", "Conflict deaths per 100,000 people, last 3 years (UCDP)", .40),
                ("instability", "Political instability (World Bank WGI, inverted)", .25),
                ("lawless", "Weak rule of law (World Bank WGI, inverted)", .15),
                ("displaced", "People displaced from the country per 1,000 (UNHCR)", .20)]
RISK_FROM = 2015
POWER_WEIGHTS = [("economy", "Economic size: GDP (World Bank)", .25), ("nuclear", "Nuclear warheads (FAS)", .15),
                 ("forces", "Armed forces personnel (World Bank/IISS)", .10), ("population", "Population (World Bank)", .10),
                 ("trade", "Exports of goods and services (World Bank)", .10), ("tech", "Resident patent applications (World Bank/WIPO)", .05),
                 ("hightech", "High-technology exports (World Bank)", .05),
                 ("diplomacy", "Diplomatic reach: permanent UN Security Council seat and membership of major groupings", .20)]


def month_bars(pts: list, w: int = 720, h: int = 240) -> str:
    """A simple bar chart of deaths per month; pts = [('YYYY-MM', value)]."""
    if not pts:
        return ""
    peak = max(v for _, v in pts) or 1
    L, B, T = 46, 24, 8
    bw = (w - L - 8) / len(pts)
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Deaths per month">']
    for k in range(5):
        v = peak * k / 4
        y = T + (1 - k / 4) * (h - T - B)
        out.append(f'<line x1="{L}" x2="{w - 8}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                   f'<text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end" class="tick">{svg.compact(v, 0)}</text>')
    for k, (m, v) in enumerate(pts):
        bh = (v / peak) * (h - T - B)
        out.append(f'<rect x="{L + k * bw + 0.5:.1f}" y="{h - B - bh:.1f}" width="{max(bw - 1, 0.6):.1f}" height="{bh:.1f}" '
                   f'class="bar-s1"><title>{m}: {v:,.0f}</title></rect>')
        if m.endswith("-01") or k == 0:
            out.append(f'<text x="{L + k * bw:.1f}" y="{h - 6}" class="tick">{m[:4]}</text>')
    out.append("</svg>")
    return "".join(out)
PAIRS = [("USA", "CHN"), ("USA", "RUS"), ("CHN", "IND"), ("IND", "PAK"), ("RUS", "UKR"), ("ISR", "IRN"),
         ("SAU", "IRN"), ("CHN", "JPN"), ("KOR", "PRK"), ("ARM", "AZE"), ("USA", "IND"), ("RUS", "IND"),
         ("CHN", "RUS"), ("USA", "IRN"), ("DEU", "FRA"), ("TUR", "GRC"), ("ETH", "ERI"), ("SDN", "SSD"),
         ("COD", "RWA"), ("COL", "VEN"), ("USA", "MEX"), ("CHN", "VNM"), ("CHN", "PHL"), ("AFG", "PAK"),
         ("IND", "BGD"), ("GBR", "USA"), ("BRA", "ARG"), ("EGY", "ETH"), ("UKR", "POL"), ("TUR", "SYR")]
GED_FIX = {"russia (soviet union)": "RUS", "yemen (north yemen)": "YEM", "dr congo (zaire)": "COD", "myanmar (burma)": "MMR",
           "cambodia (kampuchea)": "KHM", "serbia (yugoslavia)": "SRB", "bosnia-herzegovina": "BIH", "ivory coast": "CIV",
           "madagascar (malagasy)": "MDG", "zimbabwe (rhodesia)": "ZWE", "kingdom of eswatini (swaziland)": "SWZ",
           "macedonia, fyr": "MKD", "north macedonia": "MKD", "turkey": "TUR", "congo": "COG", "gambia": "GMB",
           "vietnam (north vietnam)": "VNM", "laos": "LAO", "syria": "SYR", "iran": "IRN", "russia": "RUS",
           "united states of america": "USA", "united kingdom": "GBR", "south korea": "KOR", "north korea": "PRK",
           "palestine": "PSE", "israel": "ISR", "germany (west germany)": "DEU", "czech republic": "CZE", "kosovo": "XKX",
           "cape verde": "CPV", "east timor": "TLS", "brunei": "BRN", "taiwan": None}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"\s+", " ", s).strip()


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


class Geo:
    def __init__(self, model, countries: list[dict], by_id: dict, show):
        self.m, self.countries, self.by_id, self.show = model, countries, by_id, show
        self.ids = {e["entity_id"] for e in countries}
        self.pop = {e["entity_id"]: (model.latest(e["entity_id"], "population") or (0, 0, ""))[1] for e in countries}
        self.names = {}
        for e in countries:
            for n in [e["name"], e.get("source_name") or "", *e.get("aliases", [])]:
                if n:
                    self.names[_norm(n)] = e["entity_id"]
        self.unmatched: set[str] = set()
        self.load_conflict()
        self.load_votes()
        self.load_unhcr()
        self.compute_risk()
        self.load_blocs()
        self.load_sanctions()
        self.compute_power()
        self.compute_alerts()

    def iso(self, name: str) -> str | None:
        k = _norm(name)
        if k in GED_FIX:
            return GED_FIX[k]
        if k in self.names:
            return self.names[k]
        k2 = re.sub(r"\s*\(.*\)$", "", k)
        if k2 in self.names:
            return self.names[k2]
        self.unmatched.add(name)
        return None

    # ------------------------------------------------------------------ UCDP
    def _events(self):
        z = RAW / "ucdp" / "ged261-csv.zip"
        if z.exists():
            with zipfile.ZipFile(z) as zf:
                name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
                with zf.open(name) as f:
                    for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace")):
                        yield row, False
        c = RAW / "ucdp" / "candidate.csv"
        if c.exists():
            with open(c, encoding="utf-8", errors="replace", newline="") as f:
                for row in csv.DictReader(f):
                    yield row, True

    def load_conflict(self):
        cy = defaultdict(float)                      # (iso, year) -> deaths, all types
        cyt = defaultdict(float)                     # (iso, year, type)
        world = defaultdict(lambda: defaultdict(float))
        monthly = defaultdict(float)
        cmonth = defaultdict(float)                  # (iso, 'YYYY-MM')
        conflicts = defaultdict(lambda: {"deaths": 0.0, "countries": set(), "type": None, "events": 0})
        inter = defaultdict(lambda: defaultdict(float))  # (isoA, isoB) -> year -> deaths, government vs government
        self.final_year = self.cand_year = None
        recent = []                                  # events of the last two years, for the event map
        conf_month = defaultdict(float)              # (conflict, iso, 'YYYY-MM') for crisis pages
        cand_seen = set()
        for row, cand in self._events():
            try:
                y, t, d = int(row["year"]), int(row["type_of_violence"]), _num(row["best"])
            except (KeyError, ValueError):
                continue
            ym = (row.get("date_start") or "")[:7]
            if cand:
                if row.get("id") in cand_seen:
                    continue
                cand_seen.add(row.get("id"))
                self.cand_year = max(self.cand_year or y, y)
            else:
                self.final_year = max(self.final_year or y, y)
            iso = self.iso(row.get("country", ""))
            world[y][t] += d
            if y >= 2024:
                try:
                    recent.append(((row.get("date_start") or "")[:10], float(row["latitude"]), float(row["longitude"]), d, t,
                                   (row.get("conflict_name") or "").strip(), iso))
                except (KeyError, ValueError):
                    pass
            if ym:
                monthly[ym] += d
            if iso:
                cy[(iso, y)] += d
                cyt[(iso, y, t)] += d
                if ym:
                    cmonth[(iso, ym)] += d
            key = (row.get("conflict_name") or "").strip()
            if key and ym:
                conf_month[(key, iso, ym)] += d
            if key:
                c = conflicts[(key, y)]
                c["deaths"] += d; c["type"] = t; c["events"] += 1
                if iso:
                    c["countries"].add(iso)
            a, b = row.get("side_a", ""), row.get("side_b", "")
            if t == 1 and a.startswith("Government of") and b.startswith("Government of"):
                # a side can be a coalition: "Government of Australia, Government of United Kingdom, ..."
                ga = [x for x in (self.iso(n.strip()) for n in re.findall(r"Government of ([^,]+)", a)) if x]
                gb = [x for x in (self.iso(n.strip()) for n in re.findall(r"Government of ([^,]+)", b)) if x]
                for ia in ga:
                    for ib in gb:
                        if ia != ib:
                            inter[tuple(sorted((ia, ib)))][y] += d     # every pair on opposite sides was at war
        if self.cand_year and self.final_year and self.cand_year <= self.final_year:
            self.cand_year = None
        self.cy, self.cyt, self.world_deaths, self.monthly, self.cmonth = cy, cyt, world, monthly, cmonth
        self.events = self.event_points(recent)
        self.conf_month = conf_month
        self.conflicts, self.inter = conflicts, inter

    @staticmethod
    def event_points(recent: list) -> dict:
        """Events of the last 12 months, merged onto a half-degree grid so the map stays light."""
        dates = sorted(r[0] for r in recent if r[0])
        if not dates:
            return {"points": [], "from": None, "to": None}
        end = dates[-1]
        y, mth = int(end[:4]), int(end[5:7])
        start = f"{y - 1}-{mth:02d}-{end[8:10]}"
        cells = {}
        for date, lat, lon, d, t, conflict, iso in recent:
            if not date or date <= start:
                continue
            k = (round(lat * 2) / 2, round(lon * 2) / 2)
            c = cells.setdefault(k, {"d": 0.0, "n": 0, "t": defaultdict(float), "c": defaultdict(float), "iso": iso})
            c["d"] += d; c["n"] += 1; c["t"][t] += d or 1; c["c"][conflict] += d or 1
        pts = [[k[1], k[0], round(c["d"]), c["n"], max(c["t"], key=c["t"].get), max(c["c"], key=c["c"].get), c["iso"] or ""]
               for k, c in cells.items()]
        pts.sort(key=lambda p: -p[2])
        return {"points": pts, "from": start, "to": end}

    def deaths(self, iso: str, years) -> float:
        return sum(self.cy.get((iso, y), 0.0) for y in years)

    # ------------------------------------------------------------------ UN votes
    def load_votes(self):
        self.ideal = defaultdict(dict)              # iso -> year -> ideal point
        cow = {}
        p = RAW / "unvotes" / "idealpoints.csv"
        if p.exists():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    iso = row.get("iso3c") or ""
                    if row.get("ccode"):
                        cow[row["ccode"]] = iso
                    if iso in self.ids and row.get("IdealPointFP") not in ("", "NA", None):
                        self.ideal[iso][int(row["year"])] = float(row["IdealPointFP"])
        self.agree = defaultdict(dict)              # (a, b) sorted -> year -> share of votes in agreement
        p = RAW / "unvotes" / "agreement.csv"
        self.vote_year = None
        if p.exists():
            with open(p, encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        y = int(row["year"])
                    except (KeyError, ValueError):
                        continue
                    if y < 1991 or row.get("agree") in ("", "NA"):
                        continue
                    a, b = cow.get(row["ccode1"]), cow.get(row["ccode2"])
                    if a in self.ids and b in self.ids and a != b:
                        self.agree[tuple(sorted((a, b)))][y] = float(row["agree"])
                        self.vote_year = max(self.vote_year or y, y)

    def agreement(self, a: str, b: str) -> dict:
        return self.agree.get(tuple(sorted((a, b))), {})

    def latest_agreement(self, a: str, b: str, min_year: int | None = None):
        s = self.agreement(a, b)
        if not s:
            return None
        y = max(s)
        return (y, s[y]) if min_year is None or y >= min_year else None

    # ------------------------------------------------------------------ UNHCR
    def load_unhcr(self):
        def rows(name):
            p = RAW / "unhcr" / f"{name}.json"
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        self.origin = defaultdict(dict)             # iso -> year -> {refugees, asylum, idps, oip}
        for r in rows("by_origin"):
            iso = r.get("coo_iso")
            if iso in self.ids:
                self.origin[iso][int(r["year"])] = {k: _num(r.get(src)) for k, src in
                                                     (("refugees", "refugees"), ("asylum", "asylum_seekers"),
                                                      ("idps", "idps"), ("oip", "oip"))}
        self.hosted = defaultdict(dict)
        for r in rows("by_asylum"):
            iso = r.get("coa_iso")
            if iso in self.ids:
                self.hosted[iso][int(r["year"])] = {"refugees": _num(r.get("refugees")), "asylum": _num(r.get("asylum_seekers")),
                                                    "oip": _num(r.get("oip"))}
        self.flows = defaultdict(float)
        fy = [int(r["year"]) for r in rows("flows")]
        self.flow_year = max(fy) if fy else None
        for r in rows("flows"):
            if int(r["year"]) == self.flow_year and r.get("coo_iso") in self.ids and r.get("coa_iso") in self.ids:
                self.flows[(r["coo_iso"], r["coa_iso"])] += _num(r.get("refugees")) + _num(r.get("asylum_seekers")) + _num(r.get("oip"))
        years = [y for d in self.origin.values() for y in d]
        self.unhcr_year = max(years) if years else None

    def displaced_out(self, iso: str, year: int | None = None):
        d = self.origin.get(iso, {})
        y = year or (max(d) if d else None)
        if y not in d:
            return None
        r = d[y]
        return {"year": y, "abroad": r["refugees"] + r["asylum"] + r["oip"], "idps": r["idps"]}

    def hosted_in(self, iso: str, year: int | None = None):
        d = self.hosted.get(iso, {})
        y = year or (max(d) if d else None)
        if y not in d:
            return None
        r = d[y]
        return {"year": y, "hosted": r["refugees"] + r["asylum"] + r["oip"]}

    # ------------------------------------------------------------------ risk index
    def compute_risk(self):
        """The index for every year since RISK_FROM, scaled on the pooled range of all years so that a
        country's score can be compared across time. Built only from the verified datasets."""
        fy = self.final_year or 2025
        raw = {}
        for y in range(RISK_FROM, fy + 1):
            for e in self.countries:
                i, pop = e["entity_id"], self.pop.get(e["entity_id"], 0)
                if pop < 100_000:
                    continue
                c = {"conflict": math.log1p(1e5 * self.deaths(i, range(y - 2, y + 1)) / pop / 3)}
                for key, ind in (("instability", "wgi-political-stability"), ("lawless", "wgi-rule-of-law")):
                    lt = self.m.latest(i, ind, max_year=y, min_year=y - 2) if ind in self.m.indicators else None
                    if lt:
                        c[key] = -lt[1]
                d = self.displaced_out(i, y) or self.displaced_out(i, y - 1)
                if d:
                    c["displaced"] = math.log1p(1000 * (d["abroad"] + d["idps"]) / pop)
                if "instability" in c and len(c) >= 3:
                    raw[(i, y)] = c
        keys = [k for k, _, _ in RISK_WEIGHTS]
        lo = {k: min(v[k] for v in raw.values() if k in v) for k in keys}
        hi = {k: max(v[k] for v in raw.values() if k in v) for k in keys}
        scores = {}
        for (i, y), comps in raw.items():
            norm = {k: 100 * (comps[k] - lo[k]) / ((hi[k] - lo[k]) or 1) for k in comps}
            wsum = sum(w for k, _, w in RISK_WEIGHTS if k in norm)
            scores[(i, y)] = (sum(norm[k] * w for k, _, w in RISK_WEIGHTS if k in norm) / wsum, norm)
        band = lambda sc: "Very high" if sc >= 55 else "High" if sc >= 40 else "Elevated" if sc >= 25 else "Low"
        out = []
        for e in self.countries:
            i = e["entity_id"]
            if (i, fy) not in scores:
                continue
            sc, norm = scores[(i, fy)]
            hist = [(y, round(scores[(i, y)][0], 1)) for y in range(RISK_FROM, fy + 1) if (i, y) in scores]
            base = next((v for y, v in hist if y == fy - 5), None)
            out.append({"e": e, "score": sc, "parts": norm, "band": band(sc), "hist": hist,
                        "change5": (sc - base) if base is not None else None,
                        "spark": svg.sparkline(hist, w=90, h=26, label=f"{e['name']} risk") if len(hist) > 1 else ""})
        out.sort(key=lambda r: -r["score"])
        for k, r in enumerate(out):
            r["rank"] = k + 1
        self.risk = out
        self.risk_by = {r["e"]["entity_id"]: r for r in out}
        moved = [r for r in out if r["change5"] is not None]
        self.risers = sorted(moved, key=lambda r: -r["change5"])[:10]
        self.fallers = sorted(moved, key=lambda r: r["change5"])[:10]
        self.risk_year = fy

    # ------------------------------------------------------------------ blocs, treaties, nuclear forces
    def load_blocs(self):
        cfg = load_yaml("blocs.yaml")
        self.blocs_as_of, self.treaties, self.nuclear = cfg["as_of"], cfg["treaties"], cfg["nuclear"]
        world_pop = (self.m.latest("WLD", "population") or (0, 0, ""))[1]
        world_gdp = (self.m.latest("WLD", "gdp") or (0, 0, ""))[1]
        world_exp = (self.m.latest("WLD", "exports-value") or (0, 0, ""))[1] if "exports-value" in self.m.indicators else 0
        self.blocs = []
        vy = self.vote_year
        for b in cfg["blocs"]:
            mem = [x for x in b["members"] if x in self.ids]
            status = b.get("status", {})
            tot = lambda ind: sum((self.m.latest(x, ind, min_year=2015) or (0, 0, ""))[1] for x in mem) if ind in self.m.indicators else 0
            pop, gdp, exp, forces = tot("population"), tot("gdp"), tot("exports-value"), tot("armed-forces")
            warheads = sum(self.nuclear["states"].get(x, {}).get("inventory", 0) for x in mem)
            inner = [self.agreement(a, c).get(vy) for k, a in enumerate(mem) for c in mem[k + 1:]] if vy else []
            inner = [v for v in inner if v is not None]
            withp = {}
            for pw in ("USA", "CHN", "RUS"):
                v = [self.agreement(x, pw).get(vy) for x in mem if x != pw] if vy else []
                v = [x for x in v if x is not None]
                if v:
                    withp[pw] = sum(v) / len(v)
            risks = [self.risk_by[x]["score"] for x in mem if x in self.risk_by]
            deaths = sum(self.deaths(x, range((self.final_year or 2025) - 2, (self.final_year or 2025) + 1)) for x in mem)
            self.blocs.append({**b, "mem": [self.by_id[x] for x in mem], "status": status, "people": pop, "gdp": gdp, "exp": exp,
                               "pop_share": 100 * pop / world_pop if world_pop else None,
                               "gdp_share": 100 * gdp / world_gdp if world_gdp else None,
                               "exp_share": 100 * exp / world_exp if world_exp else None,
                               "forces": forces, "warheads": warheads, "cohesion": sum(inner) / len(inner) if inner else None,
                               "with": withp, "risk": sum(risks) / len(risks) if risks else None, "deaths3": deaths,
                               "map": {x: 1 for x in mem}})
        self.bloc_of = defaultdict(list)
        for b in self.blocs:
            for e in b["mem"]:
                self.bloc_of[e["entity_id"]].append({"id": b["id"], "name": b["name"], "status": b["status"].get(e["entity_id"])})

    # ------------------------------------------------------------------ crises
    def crises(self) -> list:
        out = []
        for c in load_yaml("blocs.yaml").get("crises", []):
            isos, names = set(c["countries"]), set(c.get("conflicts", []))
            monthly = defaultdict(float)
            for (i, ym), d in self.cmonth.items():
                if i in isos:
                    monthly[ym] += d
            for (k, i, ym), d in self.conf_month.items():
                if k in names and i not in isos:
                    monthly[ym] += d
            months = sorted(m for m in monthly if int(m[:4]) >= c["since"])
            pts = [(m, monthly[m]) for m in months]
            involved = {k for (k, y), d in self.conflicts.items() if y >= c["since"] and (d["countries"] & isos or k in names)}
            conflicts = sorted(((k, sum(d["deaths"] for (kk, y), d in self.conflicts.items() if kk == k and y >= c["since"])) for k in involved),
                               key=lambda x: -x[1])[:8]
            ev = [pt for pt in self.events["points"] if pt[6] in isos or pt[5] in names]
            disp = []
            for i in c["countries"]:
                d = self.origin.get(i, {})
                ser = sorted((y, r["refugees"] + r["asylum"] + r["oip"] + r["idps"]) for y, r in d.items() if y >= c["since"] - 2)
                if i in self.by_id and ser:
                    disp.append({"e": self.by_id[i], "series": ser})
            parties = [self.by_id[i] for i in c.get("parties", []) if i in self.by_id]
            pairs = []
            for k, a in enumerate(parties):
                for b in parties[k + 1:]:
                    la = self.latest_agreement(a["entity_id"], b["entity_id"])
                    if la:
                        pairs.append({"a": a, "b": b, "year": la[0], "v": la[1]})
            out.append({**c, "monthly": pts, "chart": month_bars(pts), "total": sum(v for _, v in pts),
                        "last12": sum(v for _, v in pts[-12:]), "prev12": sum(v for _, v in pts[-24:-12]),
                        "conflicts": conflicts, "events": ev, "disp": disp, "parties": parties, "pairs": pairs,
                        "risk": [self.risk_by[i] for i in c["countries"] if i in self.risk_by],
                        "states": [self.by_id[i] for i in c["countries"] if i in self.by_id],
                        "last_month": months[-1] if months else None})
        return out

    # ------------------------------------------------------------------ US sanctions (OFAC SDN)
    def load_sanctions(self):
        sdn, add = RAW / "ofac" / "sdn.csv", RAW / "ofac" / "add.csv"
        self.sanctions = {"by_country": {}, "programs": [], "total": 0}
        if not (sdn.exists() and add.exists()):
            return
        before = set(self.unmatched)
        progs, kinds = {}, {}
        with open(sdn, encoding="latin-1", newline="") as f:
            for row in csv.reader(f):
                if len(row) > 3 and row[0].strip().isdigit():
                    progs[row[0].strip()] = [x.strip(" []") for x in row[3].split("]") if x.strip(" []")]
                    kinds[row[0].strip()] = row[2].strip().strip('"')
        where = defaultdict(set)
        with open(add, encoding="latin-1", newline="") as f:
            for row in csv.reader(f):
                if len(row) > 4 and row[0].strip().isdigit():
                    name = row[4].strip().strip('"')
                    if name and name != "-0-":
                        iso = self.iso(name)
                        if iso:
                            where[iso].add(row[0].strip())
        self.unmatched = before            # address countries the matcher misses are not conflict data problems
        by = {}
        for iso, ids in where.items():
            pc = defaultdict(int)
            for i in ids:
                for pg in progs.get(i, []):
                    pc[pg] += 1
            by[iso] = {"n": len(ids), "individuals": sum(1 for i in ids if kinds.get(i) == "individual"),
                       "programs": sorted(pc.items(), key=lambda x: -x[1])[:6]}
        allp = defaultdict(int)
        for ps in progs.values():
            for pg in ps:
                allp[pg] += 1
        self.sanctions = {"by_country": by, "programs": sorted(allp.items(), key=lambda x: -x[1])[:20], "total": len(progs)}

    # ------------------------------------------------------------------ power index
    def compute_power(self):
        nuc = self.nuclear["states"]
        diplo_w = {"g7": 3, "g20": 3, "nato": 2, "brics": 2, "sco": 2, "oecd": 1, "eu": 1, "quad": 1, "aukus": 1}
        permanent = {i for b in self.blocs if b["id"] == "unsc" for i, st in b["status"].items() if st == "permanent"}
        raw = {}
        for e in self.countries:
            i = e["entity_id"]
            if self.pop.get(i, 0) < 1e6:
                continue

            def g(ind):
                if ind not in self.m.indicators:
                    return None
                lt = self.m.latest(i, ind, min_year=2015)
                return lt[1] if lt else None
            gdp = g("gdp")
            if not gdp:
                continue
            reach = sum(diplo_w.get(b["id"], 0) for b in self.bloc_of.get(i, []))
            raw[i] = {"economy": math.log10(gdp), "population": math.log10(self.pop[i]),
                      "forces": math.log10(1 + (g("armed-forces") or 0)), "nuclear": math.log10(1 + nuc.get(i, {}).get("inventory", 0)),
                      "trade": math.log10(1 + (g("exports-value") or 0)), "tech": math.log10(1 + (g("patents-residents") or 0)),
                      "hightech": math.log10(1 + (g("high-tech-exports-value") or 0)),
                      "diplomacy": 0.5 * (i in permanent) + 0.5 * reach / sum(diplo_w.values())}
        lo = {k: min(v[k] for v in raw.values()) for k, _, _ in POWER_WEIGHTS}
        hi = {k: max(v[k] for v in raw.values()) for k, _, _ in POWER_WEIGHTS}
        out = []
        for i, c in raw.items():
            parts = {k: 100 * (c[k] - lo[k]) / ((hi[k] - lo[k]) or 1) for k in c}
            out.append({"e": self.by_id[i], "score": sum(parts[k] * w for k, _, w in POWER_WEIGHTS), "parts": parts})
        out.sort(key=lambda r: -r["score"])
        for k, r in enumerate(out):
            r["rank"] = k + 1
        self.power = out
        self.power_by = {r["e"]["entity_id"]: r for r in out}

    # ------------------------------------------------------------------ alerts
    def compute_alerts(self):
        """Countries whose risk rose sharply in the latest year, or whose conflict deaths this year are well
        above the same months of last year."""
        alerts = []
        y = self.risk_year
        for r in self.risk:
            h = dict(r["hist"])
            if y in h and y - 1 in h and h[y] - h[y - 1] >= 5:
                alerts.append({"e": r["e"], "kind": "risk", "text": f"Risk index up {h[y] - h[y - 1]:.0f} points in {y}, to {h[y]:.0f}."})
        if self.cand_year and self.final_year:
            months = sorted(k[5:] for k in self.monthly if k.startswith(str(self.cand_year)))
            for e in self.countries:
                i = e["entity_id"]
                now = sum(self.cmonth.get((i, f"{self.cand_year}-{m}"), 0) for m in months)
                before = sum(self.cmonth.get((i, f"{self.final_year}-{m}"), 0) for m in months)
                if now >= 100 and now >= 1.5 * before:
                    alerts.append({"e": e, "kind": "conflict",
                                   "text": f"{now:,.0f} conflict deaths so far in {self.cand_year}, against {before:,.0f} in the same months of {self.final_year} (UCDP, preliminary)."})
        self.alerts = alerts
        self.alerts_by = defaultdict(list)
        for a in alerts:
            self.alerts_by[a["e"]["entity_id"]].append(a)

    def treaty_status(self, iso: str) -> list:
        return [{"t": t, "status": t["outside"].get(iso, "party")} for t in self.treaties]

    def nuclear_rows(self) -> list:
        return sorted(((self.by_id[i], v) for i, v in self.nuclear["states"].items() if i in self.by_id), key=lambda x: -x[1]["inventory"])

    # ------------------------------------------------------------------ page data
    def overview(self) -> dict:
        fy = self.final_year
        w = self.world_deaths
        series = [{"label": TYPES[t], "points": [(y, w[y].get(t, 0)) for y in sorted(w) if y <= fy], "cls": f"s{k + 1}"}
                  for k, t in enumerate((1, 2, 3))]
        chart = svg.line_chart(series, "deaths", decimals=0, title="Deaths in organised violence, by type (UCDP)")
        latest = [(c, d) for (c, y), d in self.conflicts.items() if y == fy]
        latest.sort(key=lambda x: -x[1]["deaths"])
        top_conf = [{"name": c, "deaths": d["deaths"], "type": TYPES.get(d["type"], ""),
                     "countries": [self.by_id[i] for i in sorted(d["countries"]) if i in self.by_id]} for c, d in latest[:15]]
        active = sum(1 for c, d in latest if d["type"] == 1 and d["deaths"] >= 25)
        by_c = sorted(((self.by_id[i], d) for (i, y), d in self.cy.items() if y == fy and i in self.by_id and d > 0),
                      key=lambda x: -x[1])
        cand = None
        if self.cand_year:
            months = sorted(k for k in self.monthly if k.startswith(str(self.cand_year)))
            ytd = sum(self.monthly[k] for k in months)
            same = sum(self.monthly.get(f"{fy}{k[4:]}", 0) for k in months)
            top = sorted(((self.by_id[i], d) for (i, ym), d in self.cmonth.items() if ym in months and i in self.by_id),
                         key=lambda x: -x[1])
            agg = defaultdict(float)
            for e, d in top:
                agg[e["entity_id"]] += d
            ctop = sorted(((self.by_id[i], d) for i, d in agg.items()), key=lambda x: -x[1])[:12]
            prev = {e["entity_id"]: sum(self.cmonth.get((e["entity_id"], f"{fy}{k[4:]}"), 0) for k in months) for e, _ in ctop}
            cand = {"year": self.cand_year, "months": months, "ytd": ytd, "same": same, "last": months[-1] if months else None,
                    "top": [{"e": e, "d": d, "prev": prev[e["entity_id"]]} for e, d in ctop]}
        mpts = sorted(self.monthly.items())[-36:]
        month_chart = svg.line_chart([{"label": "Deaths per month", "points": [(k, v) for k, v in
                                       enumerate([v for _, v in mpts])]}], "deaths", decimals=0,
                                     title="Deaths per month, last 36 months") if mpts else ""
        total_fy = sum(w[fy].values()) if fy in w else 0
        disp = sum((self.displaced_out(i) or {}).get("abroad", 0) + (self.displaced_out(i) or {}).get("idps", 0) for i in self.ids)
        return {"final_year": fy, "chart": chart, "top_conflicts": top_conf, "active": active, "by_country": by_c[:20],
                "total": total_fy, "prev_total": sum(w.get(fy - 1, {}).values()), "cand": cand, "month_labels": [k for k, _ in mpts],
                "conflict_map": {e["entity_id"]: round(1e5 * self.deaths(e["entity_id"], range(fy - 2, fy + 1)) / self.pop[e["entity_id"]] / 3, 3)
                                 for e in self.countries if self.pop.get(e["entity_id"], 0) > 0},
                "displaced_total": disp}

    def alignment(self) -> dict:
        vy = self.vote_year
        tables = {}
        for p in POWERS:
            rows = [(self.by_id[i], la[1]) for i in self.ids if i != p and (la := self.latest_agreement(p, i, vy - 1 if vy else None))]
            rows.sort(key=lambda x: -x[1])
            tables[p] = {"name": POWER_NAMES[p], "top": rows[:10], "bottom": rows[-10:][::-1], "n": len(rows)}
        ideal = {i: s[max(s)] for i, s in self.ideal.items() if s and max(s) >= (vy or 2020) - 2}
        return {"year": vy, "tables": tables, "ideal_map": {k: round(v, 3) for k, v in ideal.items()}}

    def displacement(self) -> dict:
        y = self.unhcr_year
        origins = sorted(((self.by_id[i], d) for i in self.ids if (d := self.displaced_out(i, y))), key=lambda x: -(x[1]["abroad"] + x[1]["idps"]))
        hosts = sorted(((self.by_id[i], d) for i in self.ids if (d := self.hosted_in(i, y))), key=lambda x: -x[1]["hosted"])
        trend = defaultdict(float)
        for d in self.origin.values():
            for yy, r in d.items():
                trend[yy] += r["refugees"] + r["asylum"] + r["oip"] + r["idps"]
        chart = svg.line_chart([{"label": "Refugees, asylum seekers and internally displaced", "points": sorted(trend.items())}],
                               "people", decimals=0, title="People forcibly displaced (UNHCR)")
        flows = sorted(((self.by_id[a], self.by_id[b], v) for (a, b), v in self.flows.items() if v > 0), key=lambda x: -x[2])[:15]
        return {"year": y, "origins": origins[:20], "hosts": hosts[:20], "chart": chart, "flows": flows, "flow_year": self.flow_year}

    def country(self, iso: str) -> dict | None:
        fy = self.final_year or 2025
        d3 = self.deaths(iso, range(fy - 2, fy + 1))
        al = {p: la for p in POWERS if p != iso and (la := self.latest_agreement(iso, p))}
        r = self.risk_by.get(iso)
        disp, host = self.displaced_out(iso), self.hosted_in(iso)
        if not (r or d3 or al or disp):
            return None
        cyear = None
        if self.cand_year:
            cyear = sum(v for (i, ym), v in self.cmonth.items() if i == iso and ym.startswith(str(self.cand_year)))
        forces = self.m.latest(iso, "armed-forces", min_year=2015) if "armed-forces" in self.m.indicators else None
        return {"power": self.power_by.get(iso), "n_power": len(self.power), "sanctions": self.sanctions["by_country"].get(iso),
                "alerts": self.alerts_by.get(iso, []),
                "blocs": self.bloc_of.get(iso, []), "treaties": self.treaty_status(iso), "nuclear": self.nuclear["states"].get(iso),
                "forces": forces, "risk": r, "deaths3": d3, "years": (fy - 2, fy), "align": al, "disp": disp, "host": host,
                "cand": cyear, "cand_year": self.cand_year, "n_risk": len(self.risk)}

    def pair(self, a: str, b: str) -> dict:
        s = self.agreement(a, b)
        pts = sorted(s.items())
        chart = svg.line_chart([{"label": "Share of UN votes in agreement", "points": [(y, 100 * v) for y, v in pts]}],
                               "% of votes", decimals=0, title="UN General Assembly vote agreement") if len(pts) > 1 else ""
        war = self.inter.get(tuple(sorted((a, b))), {})
        latest = (max(s), s[max(s)]) if s else None
        # where this pair sits among each side's partners
        rank_a = rank_b = None
        if latest:
            pa = sorted((v[latest[0]] for k, v in self.agree.items() if a in k and latest[0] in v), reverse=True)
            pb = sorted((v[latest[0]] for k, v in self.agree.items() if b in k and latest[0] in v), reverse=True)
            rank_a = (pa.index(latest[1]) + 1, len(pa)) if latest[1] in pa else None
            rank_b = (pb.index(latest[1]) + 1, len(pb)) if latest[1] in pb else None
        return {"chart": chart, "latest": latest, "first": pts[0] if pts else None, "war": sorted(war.items()),
                "war_deaths": sum(war.values()), "ab": self.flows.get((a, b), 0), "ba": self.flows.get((b, a), 0),
                "ideal_a": self.ideal.get(a, {}), "ideal_b": self.ideal.get(b, {}), "rank_a": rank_a, "rank_b": rank_b,
                "risk_a": self.risk_by.get(a), "risk_b": self.risk_by.get(b)}

    def briefing(self) -> dict:
        """What changed: news attention (GDELT samples), this year's conflict vs the same months last year,
        shifts in UN alignment and new displacement."""
        out = {}
        gdir = RAW / "gdelt" / "daily"
        days = sorted(p for p in gdir.glob("*.json") if not p.name.endswith(".meta.json")) if gdir.exists() else []
        if len(days) >= 4:
            fips = {}
            with open(RAW / "wikidata" / "fips_iso3.csv", encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    if row["iso3"] in self.ids:
                        fips.setdefault(row["fips"], row["iso3"])
            def shares(p):
                d = json.loads(p.read_text(encoding="utf-8"))
                tot = d["all_articles"] or 1
                return {fips[c]: (100 * v["articles"] / tot, v["tone_x_articles"] / v["articles"] if v["articles"] else 0)
                        for c, v in d["countries"].items() if c in fips}
            recent = [shares(p) for p in days[-2:]]
            base = [shares(p) for p in days[:-2]]
            def avg(lst, iso, k):
                vals = [x[iso][k] for x in lst if iso in x]
                return sum(vals) / len(vals) if vals else None
            rows = []
            for iso in self.ids:
                r, b = avg(recent, iso, 0), avg(base, iso, 0)
                if r is not None and b and r >= 0.3:
                    rows.append({"e": self.by_id[iso], "now": r, "base": b, "x": r / b,
                                 "tone": avg(recent, iso, 1), "tone_base": avg(base, iso, 1)})
            out["attention"] = sorted(rows, key=lambda x: -x["x"])[:10]
            out["most_covered"] = sorted(rows, key=lambda x: -x["now"])[:10]
            out["tone_drop"] = sorted((x for x in rows if x["tone"] is not None and x["tone_base"] is not None),
                                      key=lambda x: x["tone"] - x["tone_base"])[:8]
            out["news_from"], out["news_to"] = days[0].stem, days[-1].stem
        ov = self.overview()
        out["conflict"] = ov["cand"]
        out["final_year"] = ov["final_year"]
        vy = self.vote_year
        shifts = []
        if vy:
            for i in self.ids:
                for p in ("USA", "CHN", "RUS"):
                    s = self.agreement(i, p)
                    if vy in s and vy - 5 in s and i != p:
                        shifts.append({"e": self.by_id[i], "p": POWER_NAMES[p], "now": s[vy], "then": s[vy - 5], "d": s[vy] - s[vy - 5]})
            shifts.sort(key=lambda x: -abs(x["d"]))
        out["shifts"], out["vote_year"] = shifts[:10], vy
        y = self.unhcr_year
        newd = []
        if y:
            for i in self.ids:
                a, b = self.displaced_out(i, y), self.displaced_out(i, y - 1)
                if a and b:
                    newd.append({"e": self.by_id[i], "now": a["abroad"] + a["idps"], "then": b["abroad"] + b["idps"]})
            newd.sort(key=lambda x: -(x["now"] - x["then"]))
        out["displacement"], out["unhcr_year"] = newd[:8], y
        return out

    def country_file(self, iso: str) -> dict:
        partners = {}
        for (a, b), s in self.agree.items():
            if iso in (a, b):
                partners[b if a == iso else a] = [[y, round(v, 3)] for y, v in sorted(s.items()) if y >= 2000]
        fy = self.final_year or 2025
        return {"id": iso, "agree": partners,
                "ideal": [[y, round(v, 3)] for y, v in sorted(self.ideal.get(iso, {}).items()) if y >= 2000],
                "deaths": [[y, round(self.cy.get((iso, y), 0))] for y in range(2000, fy + 1)],
                "out": sorted([[b, round(v)] for (a, b), v in self.flows.items() if a == iso and v > 0], key=lambda x: -x[1])[:15],
                "in": sorted([[a, round(v)] for (a, b), v in self.flows.items() if b == iso and v > 0], key=lambda x: -x[1])[:15],
                "war": {("".join(k).replace(iso, "")): [[y, round(d)] for y, d in sorted(v.items())] for k, v in self.inter.items() if iso in k},
                "risk": round(self.risk_by[iso]["score"], 1) if iso in self.risk_by else None,
                "risk_band": self.risk_by[iso]["band"] if iso in self.risk_by else None,
                "risk_rank": [self.risk_by[iso]["rank"], len(self.risk)] if iso in self.risk_by else None,
                "risk_hist": self.risk_by[iso]["hist"] if iso in self.risk_by else [],
                "blocs": [b["name"] for b in self.bloc_of.get(iso, [])],
                "name": self.by_id[iso]["name"], "slug": self.by_id[iso]["slug"],
                "cand": [self.cand_year, round(sum(v for (i, ym), v in self.cmonth.items() if i == iso and ym.startswith(str(self.cand_year))))]
                        if self.cand_year else None}

    def write_files(self, out: Path) -> None:
        out.mkdir(parents=True, exist_ok=True)
        for e in self.countries:
            (out / f"{e['entity_id']}.json").write_text(json.dumps(self.country_file(e["entity_id"]), separators=(",", ":")),
                                                         encoding="utf-8")
