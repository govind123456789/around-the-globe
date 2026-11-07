"""Historical layer: which polities held the land of each modern country, 200 BCE – 2024.

Source: Cliopatria (Seshat Global History Databank), CC BY 4.0. Each Cliopatria row is a
polity's territory over a range of years. We intersect every row with today's country
borders (Natural Earth, India point of view) using an equal-area projection, then sample
every STEP years to get the share of each country's land held by each polity.

Outputs (written by build()):
  build/history_shares.json        country -> {polity_key: [[year, share], ...]}
  dist/history/map/<year>.json     simplified world polity map per MAP_STEP years
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree

from .config import BUILD, DIST, RAW, load_yaml

START, END = -200, 2024
STEP = 5                 # sampling interval for shares (years)
MAP_STEP = 50            # interval between map snapshots (years)
MIN_SHARE = 0.02         # ignore polities holding <2% of a country's land
R = 6371.0088            # km

CLIO = RAW / "cliopatria" / "cliopatria_polities_only_v021.geojson"
MODERN = RAW / "ne" / "countries_ind_simplified.geojson"
NE_FIX = {"KOS": "XKX", "SDS": "SSD", "PSX": "PSE", "SAH": "ESH", "JEY": "CHI", "GGY": "CHI"}


def equal_area(geom):
    """Lambert cylindrical equal-area projection (km), so shapely .area is true area."""
    def f(xy):
        lon, lat = np.radians(xy[:, 0]), np.radians(np.clip(xy[:, 1], -89.9, 89.9))
        return np.column_stack([R * lon, R * np.sin(lat)])
    return shapely.make_valid(shapely.transform(geom, f))


def sample_years() -> list[int]:
    ys = list(range(START, END + 1, STEP))
    if ys[-1] != END:
        ys.append(END)
    return ys


def map_years() -> list[int]:
    ys = list(range(START, 2001, MAP_STEP))
    return ys + [END]


def load_modern(known: set[str]) -> dict[str, object]:
    gj = json.loads(MODERN.read_text(encoding="utf-8"))
    out = {}
    for f in gj["features"]:
        if not f.get("geometry"):
            continue
        p = f["properties"]
        code = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
        code = NE_FIX.get(code, code)
        if code not in known:
            continue
        g = shapely.make_valid(shape(f["geometry"]))
        out[code] = shapely.union(out[code], g) if code in out else g
    return out


def polity_key(props: dict) -> str:
    # Cliopatria identifies an entity by Name; Wikidata ids are metadata and some rows share
    # an id across different polities, so they must not be used as the key.
    return props["Name"]


def build(known_countries: set[str]) -> dict:
    """Return {'shares': ..., 'polities': ...} and write map snapshots."""
    modern = load_modern(known_countries)
    codes = sorted(modern)
    modern_ea = [equal_area(modern[c]) for c in codes]
    modern_area = [g.area for g in modern_ea]
    tree = STRtree(modern_ea)

    gj = json.loads(CLIO.read_text(encoding="utf-8"))
    rows = [f for f in gj["features"]
            if f["properties"].get("Type") == "POLITY"
            and f["properties"]["ToYear"] >= START and f["properties"]["FromYear"] <= END]
    print(f"  Cliopatria: {len(rows):,} polity records overlap {START}..{END}")

    years = sample_years()
    shares: dict[str, dict[str, dict[int, float]]] = {c: {} for c in codes}
    polities: dict[str, dict] = {}
    mys = map_years()
    snapshots: dict[int, list] = {y: [] for y in mys}

    for n, f in enumerate(rows, 1):
        p = f["properties"]
        key = polity_key(p)
        info = polities.setdefault(key, {"key": key, "name": p["Name"], "wikidata": p.get("Wikidata") or None,
                                         "wikipedia": p.get("Wikipedia") or None, "from": p["FromYear"],
                                         "to": p["ToYear"]})
        if p["ToYear"] >= info["to"]:          # links from the most recent row
            info["wikidata"] = p.get("Wikidata") or info["wikidata"]
            info["wikipedia"] = p.get("Wikipedia") or info["wikipedia"]
        info["from"], info["to"] = min(info["from"], p["FromYear"]), max(info["to"], p["ToYear"])
        geom = shapely.make_valid(shape(f["geometry"]))
        ys = [y for y in years if p["FromYear"] <= y <= p["ToYear"]]
        snap_ys = [y for y in mys if p["FromYear"] <= y <= p["ToYear"]]
        if snap_ys:
            simple = shapely.simplify(geom, 0.05, preserve_topology=True)
            simple = shapely.set_precision(simple, 0.01)
            if not simple.is_empty:
                for y in snap_ys:
                    snapshots[y].append({"type": "Feature", "properties": {"k": key, "n": p["Name"]},
                                         "geometry": mapping(simple)})
        if not ys:
            continue
        g_ea = equal_area(geom)
        for i in tree.query(g_ea, predicate="intersects"):
            try:
                inter = shapely.intersection(modern_ea[i], g_ea)
            except shapely.errors.GEOSException:
                inter = shapely.intersection(modern_ea[i], g_ea, grid_size=0.5)   # 0.5 km grid
            share = inter.area / modern_area[i] if modern_area[i] else 0
            if share < MIN_SHARE:
                continue
            series = shares[codes[i]].setdefault(key, {})
            for y in ys:
                series[y] = max(series.get(y, 0), round(min(share, 1.0), 4))
        if n % 2000 == 0:
            print(f"    {n:,}/{len(rows):,}")

    out_dir = DIST / "history" / "map"
    out_dir.mkdir(parents=True, exist_ok=True)
    for y, feats in snapshots.items():
        # Draw large polygons first so smaller, more specific polities sit on top. This also
        # keeps a newly independent state visible above a stale colonial row covering it.
        feats.sort(key=lambda f: -shape(f["geometry"]).area)
        (out_dir / f"{y}.json").write_text(json.dumps({"type": "FeatureCollection", "year": y, "features": feats},
                                                      separators=(",", ":")), encoding="utf-8")
    result = {
        "years": years,
        "map_years": mys,
        "polities": polities,
        "shares": {c: {k: sorted(v.items()) for k, v in s.items()} for c, s in shares.items()},
        "bbox": {c: [round(x, 2) for x in modern[c].bounds] for c in codes},
    }
    BUILD.mkdir(exist_ok=True)
    (BUILD / "history_shares.json").write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    return result


def spans(series: list[tuple[int, float]], step: int = STEP, tol: float = 0.15) -> list[list]:
    """Collapse [(year, share)] samples into [[from, to, max_share]] runs. A run continues while
    samples are consecutive and the share stays within `tol` of the run's first value, so a
    brief occupation (e.g. Iraq in Kuwait, 1990) is not merged with decades of border overlap."""
    out: list[list] = []
    base = None
    for y, s in series:
        if out and y - out[-1][1] <= step and abs(s - base) <= tol:
            out[-1][1] = y
            out[-1][2] = max(out[-1][2], s)
        else:
            out.append([y, y, s])
            base = s
    return out


MIN_RUN = 3     # samples (15 years): shorter overlaps are row-boundary effects, e.g. 1940


def home_countries(shares: dict[str, dict[str, list]]) -> dict[tuple[str, int], set[str]]:
    """(polity, year) -> countries where that polity held >=50% of the land that year."""
    out: dict[tuple[str, int], set[str]] = {}
    for iso, by_key in shares.items():
        for k, ser in by_key.items():
            for y, s in ser:
                if s >= 0.5:
                    out.setdefault((k, y), set()).add(iso)
    return out


def drop_superseded(iso: str, series_by_key: dict[str, list], homes: dict, end: int = END,
                    keep_keys: frozenset = frozenset()):
    """Consistency check for Cliopatria rows that outlive the territory they describe
    (e.g. a 1961–2023 "French Fifth Republic" row that still includes independent Algeria).

    A sample is removed only when all of these hold:
      * the country's present-day state (the polity holding >=50% at `end`) also holds >=50%
        in that same year, so Cliopatria is counting the land twice;
      * the other polity also held >=50% of a *different* country that year (it is based
        elsewhere, like France or Britain, not a regime of the same state);
      * the double counting lasts at least MIN_RUN consecutive samples.
    Returns (cleaned series, samples removed from non-umbrella polities, their names)."""
    current = [k for k, ser in series_by_key.items() if ser and ser[-1][0] == end and ser[-1][1] >= 0.5]
    if not current:
        return series_by_key, 0, []
    held = {y for k in current for y, s in series_by_key[k] if s >= 0.5}
    removed, out, hidden_from = 0, {}, []
    for k, ser in series_by_key.items():
        if k in current or k in keep_keys:
            out[k] = ser
            continue
        flag = [s >= 0.5 and y in held and bool(homes.get((k, y), set()) - {iso}) for y, s in ser]
        drop = [False] * len(ser)
        i = 0
        while i < len(ser):                      # only drop runs of MIN_RUN+ consecutive flagged samples
            if not flag[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(ser) and flag[j + 1] and ser[j + 1][0] - ser[j][0] <= STEP:
                j += 1
            if j - i + 1 >= MIN_RUN:
                for t in range(i, j + 1):
                    drop[t] = True
            i = j + 1
        keep = [x for x, d in zip(ser, drop) if not d]
        if not k.startswith("(") and len(keep) != len(ser):   # umbrellas are hidden without counting
            removed += len(ser) - len(keep)
            hidden_from.append(k)
        if keep:
            out[k] = keep
    return out, removed, hidden_from


# ============================================================================ assembly
UCDP_NAME_FIX = {"bosnia-herzegovina": "BIH", "congo": "COG", "dr congo": "COD", "hyderabad": "IND",
                 "ivory coast": "CIV", "north korea": "PRK", "south korea": "KOR", "south vietnam": "VNM",
                 "south yemen": "YEM", "united states of america": "USA"}
UCDP_TYPE = {"1": "extrasystemic (colonial)", "2": "interstate", "3": "intrastate", "4": "internationalised intrastate"}
UCDP_INCOMP = {"1": "territory", "2": "government", "3": "territory and government"}
EVENT_KIND_ORDER = {"war": 0, "rebellion": 1, "revolution": 2, "coup": 3}


def wd_year(ts: str) -> int | None:
    """Wikidata xsd:dateTime year to historical year. WDQS uses astronomical numbering
    (year 0 exists), so -0199 is 200 BCE; Cliopatria writes that as -200."""
    if not ts:
        return None
    neg = ts.startswith("-")
    y = int(ts.lstrip("-").split("-")[0])
    if neg:
        return -(y + 1)
    return y if y > 0 else -1


def load_events(known: set[str]) -> dict[str, list[dict]]:
    import csv
    by_ev: dict[str, dict] = {}
    with open(RAW / "wikidata" / "events.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            qid = r["ev"].rsplit("/", 1)[1]
            label = r["evLabel"]
            if label == qid or r["iso3"] not in known:      # no English label
                continue
            start = wd_year(r["start"])
            if start is None or start < START:
                continue
            ev = by_ev.setdefault(qid, {"id": qid, "name": label, "kind": r["kind"], "start": start,
                                        "end": wd_year(r["end"]), "countries": set(), "deaths": None,
                                        "url": r["article"] or f"https://www.wikidata.org/wiki/{qid}"})
            ev["countries"].add(r["iso3"])
            ev["start"] = min(ev["start"], start)
            if EVENT_KIND_ORDER.get(r["kind"], 9) < EVENT_KIND_ORDER.get(ev["kind"], 9):
                ev["kind"] = r["kind"]
            if r["deaths"]:
                try:
                    ev["deaths"] = max(ev["deaths"] or 0, float(r["deaths"]))
                except ValueError:
                    pass
            if r["article"] and "wikipedia.org" in r["article"]:
                ev["url"] = r["article"]
    out: dict[str, list[dict]] = {}
    for ev in by_ev.values():
        ev["countries"] = sorted(ev["countries"])
        for c in ev["countries"]:
            out.setdefault(c, []).append(ev)
    for c in out:
        out[c].sort(key=lambda e: (e["start"], e["name"]))
    return out


def load_ucdp(name_to_iso: dict[str, str]) -> dict[str, list[dict]]:
    """UCDP/PRIO armed conflicts (1946-) with battle deaths (1989-), grouped by conflict."""
    import csv
    import re
    conflicts: dict[str, dict] = {}
    with open(RAW / "ucdp" / "UcdpPrioConflict_v26_1.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            c = conflicts.setdefault(r["conflict_id"], {
                "id": r["conflict_id"], "side_a": r["side_a"], "side_b": set(), "territory": r["territory_name"] or None,
                "type": UCDP_TYPE.get(r["type_of_conflict"], ""), "incompatibility": UCDP_INCOMP.get(r["incompatibility"], ""),
                "years": set(), "war_years": set(), "countries": set(), "start": r["start_date"][:10]})
            c["side_b"].update(s.strip() for s in r["side_b"].split(","))
            y = int(r["year"])
            c["years"].add(y)
            if r["intensity_level"] == "2":          # 1,000+ battle deaths in the year
                c["war_years"].add(y)
            for loc in r["location"].split(","):
                base = re.sub(r"\s*\(.*\)", "", loc).strip().lower()
                iso = UCDP_NAME_FIX.get(base) or name_to_iso.get(base)
                if iso:
                    c["countries"].add(iso)
    deaths: dict[str, list[float]] = {}
    with open(RAW / "ucdp" / "BattleDeaths_v26_1_conf.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            d = deaths.setdefault(r["conflict_id"], [0, 0, 0])
            for i, k in enumerate(("bd_low", "bd_best", "bd_high")):
                d[i] += float(r[k] or 0)
    out: dict[str, list[dict]] = {}
    for c in conflicts.values():
        ys = sorted(c["years"])
        rec = {"id": c["id"], "side_a": c["side_a"], "side_b": sorted(c["side_b"]), "territory": c["territory"],
               "type": c["type"], "incompatibility": c["incompatibility"], "start": c["start"],
               "first": ys[0], "last": ys[-1], "active_years": len(ys), "war_years": len(c["war_years"]),
               "deaths_1989": deaths.get(c["id"]), "countries": sorted(c["countries"])}
        for iso in c["countries"]:
            out.setdefault(iso, []).append(rec)
    for iso in out:
        out[iso].sort(key=lambda x: (x["first"], x["id"]))
    return out


def load_maddison() -> dict[str, dict[str, list]]:
    import openpyxl
    wb = openpyxl.load_workbook(RAW / "maddison" / "mpd2023_web.xlsx", read_only=True)
    rows = wb["Full data"].iter_rows(values_only=True)
    next(rows)
    out: dict[str, dict[str, list]] = {}
    for code, _name, _region, year, gdppc, pop in rows:
        if year is None:
            continue
        d = out.setdefault(code, {"gdppc": [], "pop": []})
        if gdppc is not None:
            d["gdppc"].append([int(year), round(float(gdppc), 1)])
        if pop is not None:
            d["pop"].append([int(year), round(float(pop) * 1000)])     # Maddison population is in thousands
    return out


def assemble(entities: dict[str, dict]) -> dict[str, dict]:
    """Per-country history: polity spans, events, conflicts, long-run series.
    Writes dist/history/country/<ISO3>.json and returns the same records."""
    known = {e for e, v in entities.items() if v["type"] == "country"}
    src = BUILD / "history_shares.json"
    inputs = [CLIO, MODERN, Path(__file__)]
    if not src.exists() or src.stat().st_mtime < max(p.stat().st_mtime for p in inputs) \
            or not (DIST / "history" / "map").exists():
        print("  overlaying Cliopatria polities on modern borders (about 2 minutes)")
        shares = build(known)
    else:
        shares = json.loads(src.read_text(encoding="utf-8"))
    name_to_iso = {v["name"].lower(): k for k, v in entities.items() if v["type"] == "country"}
    name_to_iso.update({v["source_name"].lower(): k for k, v in entities.items() if v["type"] == "country"})
    for f in json.loads(MODERN.read_text(encoding="utf-8"))["features"]:
        p = f["properties"]
        code = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
        name_to_iso.setdefault(p["NAME"].lower(), NE_FIX.get(code, code))
    events = load_events(known)
    ucdp = load_ucdp(name_to_iso)
    mad = load_maddison()
    P = shares["polities"]
    homes = home_countries(shares["shares"])
    overrides = load_yaml("history_overrides.yaml")
    out = {}
    cdir = DIST / "history" / "country"
    cdir.mkdir(parents=True, exist_ok=True)
    for iso in sorted(known):
        rows = []
        cleaned, hidden, hidden_from = drop_superseded(
            iso, {k: [tuple(x) for x in v] for k, v in shares["shares"].get(iso, {}).items()}, homes,
            keep_keys=frozenset(k for c, k, _ in overrides.get("keep", []) if c == iso))
        for key, series in cleaned.items():
            peak = max(s for _, s in series)
            if peak < 0.10:
                continue
            sp = [x for x in spans(series) if x[2] >= 0.05]
            if not sp:
                continue
            p = P[key]
            rows.append({"key": key, "name": p["name"].strip("()"), "umbrella": p["name"].startswith("("),
                         "wikidata": p["wikidata"], "wikipedia": p["wikipedia"], "peak": round(peak, 2),
                         "spans": [[a, b, round(m, 2)] for a, b, m in sp], "first": sp[0][0], "last": sp[-1][1]})
        rows.sort(key=lambda r: (r["first"], r["umbrella"], -r["peak"]))
        rec = {"iso3": iso, "range": [START, END], "map_years": shares["map_years"], "bbox": shares["bbox"].get(iso),
               "polities": rows, "hidden_samples": hidden, "hidden_from": hidden_from, "events": events.get(iso, []), "conflicts": ucdp.get(iso, []),
               "longrun": mad.get(iso, {"gdppc": [], "pop": []})}
        out[iso] = rec
        (cdir / f"{iso}.json").write_text(json.dumps(rec, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  history: {len(out)} countries, {len(P)} polities, "
          f"{sum(len(r['events']) for r in out.values()):,} country-event links, "
          f"{sum(len(r['conflicts']) for r in out.values()):,} country-conflict links")
    return out


if __name__ == "__main__":
    import time
    t = time.time()
    countries = json.loads((RAW / "wb" / "countries.json").read_text(encoding="utf-8"))[1]
    known = {r["id"] for r in countries if r["region"]["id"] != "NA"}
    res = build(known)
    print(f"done in {time.time() - t:.0f}s; {len(res['polities'])} polities")
