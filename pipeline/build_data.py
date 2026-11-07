"""Stage 2: raw files → validated tables → licence gate → rankings → release files.

Produces a `Model` (everything the site builder needs) and writes the public
data release to dist/v1/releases/<date>/ (mirrored to dist/v1/latest/).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import duckdb

from . import engine, facts
from .config import BUILD, DIST, RAW, RELEASE, load_yaml

YEAR_MIN, YEAR_MAX = 1990, 2026
REF_YEAR, REF_AGE = 2026, 8     # rankings use each country's latest value from 2018 to 2026


class GateError(RuntimeError):
    pass


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s


def _meta(path: Path) -> dict:
    return json.loads(path.with_suffix(path.suffix + ".meta.json").read_text())


@dataclass
class Model:
    release: str
    sources: dict[str, dict]
    source_releases: dict[str, dict]
    dimensions: list[dict]
    indicators: dict[str, dict]
    entities: dict[str, dict]                  # countries + groups
    groups: dict[str, list[str]]               # group id -> member ids
    obs: dict[tuple[str, str], list[tuple[int, float, str]]]   # (entity, indicator) -> [(year, value, status)] sorted
    rejects: list[dict]
    rankings: dict[str, dict] = field(default_factory=dict)
    hdi_check: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    facts: dict[str, dict] = field(default_factory=dict)

    def countries(self) -> list[dict]:
        return sorted((e for e in self.entities.values() if e["type"] == "country"),
                      key=lambda e: unicodedata.normalize("NFKD", e["name"]).casefold())

    def series(self, entity_id: str, indicator_id: str) -> list[tuple[int, float, str]]:
        return self.obs.get((entity_id, indicator_id), [])

    def latest(self, entity_id: str, indicator_id: str, max_year: int | None = None,
               min_year: int | None = None) -> tuple[int, float, str] | None:
        for y, v, s in reversed(self.series(entity_id, indicator_id)):
            if max_year is not None and y > max_year:
                continue
            if min_year is not None and y < min_year:
                return None
            return (y, v, s)
        return None


# ----------------------------------------------------------------------------- load
def load_entities() -> tuple[dict, dict]:
    path = RAW / "wb" / "countries.json"
    rows = json.loads(path.read_text(encoding="utf-8"))[1]
    entities, groups = {}, {}
    overrides = load_yaml("country_names.yaml")["names"]
    for r in rows:
        if r["region"]["id"] == "NA":          # aggregates
            continue
        region = r["region"]["value"].strip()
        income = r["incomeLevel"]["value"].strip()
        gid_r = "R-" + r["region"]["id"]
        gid_i = "I-" + r["incomeLevel"]["id"]
        for gid, gname, kind in ((gid_r, region, "region"), (gid_i, income, "income")):
            if gid not in entities and gname and gname != "Not classified":
                entities[gid] = {"entity_id": gid, "type": "country_group", "slug": slugify(gname),
                                 "name": gname, "iso3": None, "group_kind": kind}
                groups[gid] = []
        over = overrides.get(r["id"], {})
        name = over.get("name", r["name"])
        e = {
            "entity_id": r["id"], "type": "country", "slug": slugify(name), "name": name,
            "source_name": r["name"], "aliases": over.get("aliases", []),
            "iso3": r["id"], "iso2": r["iso2Code"], "region": region, "region_id": gid_r,
            "income": income, "income_id": gid_i if gid_i in entities else None,
            "capital": r["capitalCity"] or None,
            "lat": float(r["latitude"]) if r["latitude"] else None,
            "lon": float(r["longitude"]) if r["longitude"] else None,
        }
        entities[e["entity_id"]] = e
        groups[gid_r].append(e["entity_id"])
        if e["income_id"]:
            groups[e["income_id"]].append(e["entity_id"])
    entities["WLD"] = {"entity_id": "WLD", "type": "country_group", "slug": "world", "name": "World",
                       "iso3": None, "group_kind": "world"}
    slugs = [e["slug"] for e in entities.values() if e["type"] == "country"]
    assert len(slugs) == len(set(slugs)), "duplicate country slug"
    return entities, groups


CC_BY_4 = {"CC BY-4.0", "CC BY 4.0", "CC-BY-4.0", "CC BY-4.0 "}


def check_series_licences(cat: dict, warnings: list[str]) -> list[dict]:
    """World Bank series each carry their own licence (LIC-4). Drop any that is not CC BY 4.0,
    so the source-level 'green' tier never covers a series with different terms."""
    kept = []
    for ind in cat["indicators"]:
        if ind["source"] in ("wb-wdi", "wb-wgi"):
            f = RAW / "wb" / "licence" / f"{ind['code']}.json"
            lic = json.loads(f.read_text(encoding="utf-8")).get("License_Type") if f.exists() else None
            if (lic or "").strip() not in CC_BY_4:
                warnings.append(f"{ind['id']} ({ind['code']}) excluded: series licence is {lic or 'unknown'}")
                continue
            ind["series_licence"] = "CC BY 4.0"
        kept.append(ind)
    cat["indicators"] = kept
    return kept


def load_observations(cat: dict, entities: dict, sources: dict):
    obs: dict[tuple[str, str], dict[int, tuple[float, str]]] = {}
    rejects: list[dict] = []
    source_releases: dict[str, dict] = {}
    by_code = {(i["source"], i["code"]): i for i in cat["indicators"]}

    def add(ind: dict, iso3: str, year: int, value, release_id: str):
        lo, hi = (float(b) for b in ind["bounds"])
        reason = None
        if iso3 not in entities:
            reason = "unknown_entity"
        elif not (YEAR_MIN <= year <= YEAR_MAX):
            reason = "year_out_of_range"
        elif iso3 != "WLD" and not (lo <= value <= hi):      # bounds are for countries, not world totals
            reason = "out_of_bounds"
        if reason:
            rejects.append({"source_release_id": release_id, "indicator_id": ind["id"], "entity": iso3,
                            "year": year, "value": value, "rule": reason})
            return
        key = (iso3, ind["id"])
        cell = obs.setdefault(key, {})
        if year in cell:
            rejects.append({"source_release_id": release_id, "indicator_id": ind["id"], "entity": iso3,
                            "year": year, "value": value, "rule": "duplicate_period"})
            return
        cell[year] = (value, ind.get("status", "measured"))

    # World Bank (WDI and WGI)
    for ind in cat["indicators"]:
        if ind["source"] not in ("wb-wdi", "wb-wgi"):
            continue
        path = RAW / "wb" / f"{ind['code']}.json"
        meta = _meta(path)
        rid = f"{ind['source']}:{ind['code']}@{meta['retrieved_at'][:10]}"
        payload = json.loads(path.read_text(encoding="utf-8"))
        source_releases[rid] = {"source_release_id": rid, "source_id": ind["source"], "release_label": ind["code"],
                                "retrieved_at": meta["retrieved_at"], "raw_path": str(path.relative_to(RAW)).replace("\\", "/"),
                                "checksum_sha256": meta["sha256"]}
        ind["_release"] = rid
        ind["_retrieved_at"] = meta["retrieved_at"]
        lastupd = (payload.get("indicator_meta") or {}).get("sourceOrganization")
        if lastupd:
            ind["source_org"] = lastupd
        for row in payload["rows"]:
            iso3 = row.get("countryiso3code")
            if row.get("value") is None or not iso3:
                continue
            if iso3 not in entities:      # aggregates come through here too — skip silently
                continue
            add(ind, iso3, int(row["date"]), float(row["value"]), rid)

    # UNDP HDR
    path = RAW / "undp" / "hdr25_composite_time_series.csv"
    meta = _meta(path)
    rid = f"undp-hdr:HDR25@{meta['retrieved_at'][:10]}"
    source_releases[rid] = {"source_release_id": rid, "source_id": "undp-hdr", "release_label": "HDR 2025",
                            "retrieved_at": meta["retrieved_at"], "raw_path": "undp/hdr25_composite_time_series.csv",
                            "checksum_sha256": meta["sha256"]}
    hdr_inds = [i for i in cat["indicators"] if i["source"] == "undp-hdr"]
    for i in hdr_inds:
        i["_release"], i["_retrieved_at"] = rid, meta["retrieved_at"]
    hdr_rank = {}
    with open(path, encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f):
            iso3 = "WLD" if row["iso3"] == "ZZK.WORLD" else row["iso3"]
            if not re.fullmatch(r"[A-Z]{3}", iso3):
                continue
            for idx in ("hdi", "gii"):                      # UNDP publishes these two ranks
                if row.get(f"{idx}_rank_2023"):
                    hdr_rank.setdefault(idx, {})[iso3] = int(row[f"{idx}_rank_2023"])
            for ind in hdr_inds:
                for y in range(YEAR_MIN, 2024):
                    v = row.get(f"{ind['code']}_{y}")
                    if v not in (None, ""):
                        add(ind, iso3, y, float(v), rid)

    # Transparency International CPI (via Our World in Data's republication)
    def release(source_id: str, label: str, path: Path) -> str:
        meta = _meta(path)
        rid = f"{source_id}:{label}@{meta['retrieved_at'][:10]}"
        source_releases[rid] = {"source_release_id": rid, "source_id": source_id, "release_label": label,
                                "retrieved_at": meta["retrieved_at"],
                                "raw_path": path.relative_to(RAW).as_posix(), "checksum_sha256": meta["sha256"]}
        for i in cat["indicators"]:
            if i["source"] == source_id and (source_id != "oecd" or path.stem == i["id"])                     and (source_id != "gdelt" or "_release" not in i):
                i["_release"], i["_retrieved_at"] = rid, meta["retrieved_at"]
        return rid

    by_id = {i["id"]: i for i in cat["indicators"]}
    path = RAW / "ti" / "cpi.csv"
    if path.exists() and "cpi" in by_id:
        rid = release("ti-cpi", "CPI", path)
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                code, year = row["code"], int(row["year"])
                if code in entities and year >= 2012 and row["cpi_score"] != "":
                    add(by_id["cpi"], code, year, float(row["cpi_score"]), rid)

    # OECD SDMX CSV files, one per indicator
    for ind in cat["indicators"]:
        if ind["source"] != "oecd":
            continue
        path = RAW / "oecd" / f"{ind['id']}.csv"
        rid = release("oecd", ind["id"], path)
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row["REF_AREA"] in entities and row["OBS_VALUE"] not in ("", None):
                    add(ind, row["REF_AREA"], int(row["TIME_PERIOD"][:4]), float(row["OBS_VALUE"]), rid)

    # GDELT: daily per-FIPS event totals -> one value per country for the fetch year
    gdir = RAW / "gdelt" / "daily"
    daily = sorted(p for p in gdir.glob("*.json") if not p.name.endswith(".meta.json")) if gdir.exists() else []
    if daily and "news-share" in by_id:
        fips = {}
        with open(RAW / "wikidata" / "fips_iso3.csv", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["iso3"] in entities:
                    fips.setdefault(row["fips"], row["iso3"])
        rid = release("gdelt", f"events {daily[0].stem}-{daily[-1].stem} ({len(daily)} days)", daily[-1])
        arts, tone, total = {}, {}, 0
        for path in daily:
            d = json.loads(path.read_text(encoding="utf-8"))
            total += d["all_articles"]
            for code, v in d["countries"].items():
                iso3 = fips.get(code)
                if iso3:
                    arts[iso3] = arts.get(iso3, 0) + v["articles"]
                    tone[iso3] = tone.get(iso3, 0) + v["tone_x_articles"]
        year = int(daily[-1].stem[:4])
        for iso3, n in arts.items():
            add(by_id["news-share"], iso3, year, round(100 * n / total, 6), rid)
            add(by_id["news-tone"], iso3, year, round(tone[iso3] / n, 4), rid)

    sorted_obs = {k: sorted((y, v, s) for y, (v, s) in cell.items()) for k, cell in obs.items()}
    return sorted_obs, rejects, source_releases, hdr_rank


# ----------------------------------------------------------------------------- gate
def licence_gate(model: Model, rankings_cfg: dict, strict: bool, schema_sql: Path) -> None:
    """Load tables into DuckDB with the published schema and run its gate views."""
    con = duckdb.connect()
    con.execute(schema_sql.read_text(encoding="utf-8"))
    for s in model.sources.values():
        con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            s["source_id"], s["publisher"], s["title"], s["url"], s["licence"], s.get("licence_url"),
            s["tier"], s["commercial_ok"], s["derivatives_ok"], s["share_alike"], s.get("no_modification", False),
            s["attribution_text"] or "-", s.get("licence_checked_on") or "1970-01-01", s.get("notes")])
    for r in model.source_releases.values():
        con.execute("INSERT INTO source_releases VALUES (?,?,?,?,?,?,?,?,0)", [
            r["source_release_id"], r["source_id"], r["release_label"], None, r["retrieved_at"][:19],
            r["raw_path"], r["checksum_sha256"], None])
    for e in model.entities.values():
        con.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?,?)", [
            e["entity_id"], e["type"], e["slug"], e["name"], e.get("iso3"), None, None, None])
    for i in model.indicators.values():
        con.execute("INSERT INTO indicators VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            i["id"], i["source"], i["code"], None, i["name"], i["definition"], i["unit"],
            i["direction"], i["dimension"], ["country"], i.get("transform"), float(i["bounds"][0]), float(i["bounds"][1]),
            i.get("decimals", 2), i.get("display_only", False)])
    # observations: one row per (entity, indicator) is enough for the gate's purpose
    rows = [(e, ind, ser[-1][0], ser[-1][1], ser[-1][2], model.indicators[ind]["_release"])
            for (e, ind), ser in model.obs.items()]
    con.executemany("INSERT INTO observations VALUES (?,?,?,?,?,?,NULL)", rows)
    for comp in rankings_cfg["composites"]:
        con.execute("INSERT INTO rankings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            comp["id"], comp["version"], comp["kind"], comp["name"], comp["entity_type"], None,
            json.dumps(comp.get("eligibility", {})), comp["normalisation"], comp["aggregation"],
            comp["min_coverage"], comp["mc"]["runs"], comp["mc"]["spread"], comp["mc"]["seed"],
            comp["reference_year"], comp["max_data_age"], "CC-BY-4.0", f"content/methodology/{comp['id']}.md", None])
        for p in comp["pillars"]:
            for ind in p["indicators"]:
                con.execute("INSERT INTO ranking_weights VALUES (?,?,?,?,?,?,NULL,NULL)",
                            [comp["id"], comp["version"], p["id"], p["weight"], ind["id"], ind["weight"]])
    failures = []
    for view in ("gate_non_green_published", "gate_licence_leak_into_composite",
                 "gate_inapplicable_indicator", "gate_bad_weights"):
        bad = con.execute(f"SELECT * FROM {view}").fetchall()
        if bad:
            failures.append(f"{view}: {bad[:5]}")
    unchecked = [s["source_id"] for s in model.sources.values()
                 if s["tier"] == "green" and not s.get("licence_checked_on")
                 and any(i["source"] == s["source_id"] for i in model.indicators.values())]
    if unchecked:
        msg = f"licence_checked_on not set for: {', '.join(unchecked)}"
        if strict:
            failures.append(msg)
        else:
            model.warnings.append(msg)
    if failures:
        raise GateError("Licence gate failed:\n  " + "\n  ".join(failures))
    print("  licence gate: passed" + (f" ({len(model.warnings)} warning)" if model.warnings else ""))


# ----------------------------------------------------------------------------- rankings
def _window_values(model: Model, ind_id: str, entities: list[str], ref: int, age: int):
    vals, years = {}, {}
    for e in entities:
        lt = model.latest(e, ind_id, max_year=ref, min_year=ref - age)
        if lt:
            years[e], vals[e] = lt[0], lt[1]
    return vals, years


def build_composite(model: Model, comp: dict) -> dict:
    ref, age = comp["reference_year"], comp["max_data_age"]
    min_pop = comp.get("eligibility", {}).get("min_population", 0)
    countries = [c["entity_id"] for c in model.countries()]
    eligible, ineligible = [], []
    for e in countries:
        pop = model.latest(e, "population", max_year=ref)
        (eligible if pop and pop[1] >= min_pop else ineligible).append(e)
    specs, pillars, norm, used_years = [], [], {}, {}
    for p in comp["pillars"]:
        pillars.append(engine.PillarSpec(p["id"], p["weight"]))
        for ind in p["indicators"]:
            meta = model.indicators[ind["id"]]
            spec = engine.IndicatorSpec(ind["id"], ind["weight"], meta["direction"], meta.get("transform"), p["id"])
            specs.append(spec)
            vals, years = _window_values(model, ind["id"], eligible, ref, age)
            norm[ind["id"]] = engine.normalise(vals, comp["normalisation"], spec.direction, spec.transform)
            used_years[ind["id"]] = years
    agg = "arithmetic" if comp["aggregation"] == "pillars" else comp["aggregation"]
    results = engine.score(norm, specs, pillars, eligible, comp["min_coverage"], agg)
    mc = comp["mc"]
    bands = engine.sensitivity(norm, specs, pillars, eligible, comp["min_coverage"], agg,
                               mc["runs"], mc["spread"], mc["seed"])
    rows = []
    for r in results:
        lo_hi = bands.get(r.entity_id)
        rows.append({
            "entity_id": r.entity_id, "rank": r.rank, "is_tied": r.is_tied,
            "score": None if r.score is None else round(r.score, 2), "coverage": round(r.coverage, 3),
            "excluded_reason": r.excluded_reason,
            "pillar_scores": {k: round(v, 1) for k, v in r.pillar_scores.items()},
            "rank_low": lo_hi[0] if lo_hi and r.rank else None,
            "rank_high": lo_hi[1] if lo_hi and r.rank else None,
            "movement": None,
            "indicator_values": {i.id: [used_years[i.id][r.entity_id], _vals_cache(model, r.entity_id, i.id, used_years)]
                                 for i in specs if r.entity_id in used_years[i.id]},
        })
    for e in sorted(ineligible):
        rows.append({"entity_id": e, "rank": None, "is_tied": False, "score": None, "coverage": 0.0,
                     "excluded_reason": "ineligible_population", "pillar_scores": {}, "rank_low": None,
                     "rank_high": None, "movement": None, "indicator_values": {}})
    ranked = [r for r in rows if r["rank"]]
    top10 = [r["entity_id"] for r in ranked[:10]]
    stable = sum(1 for r in ranked[:10] if r["rank_high"] and r["rank_high"] <= 10)
    return {
        "ranking_id": comp["id"], "version": comp["version"], "kind": comp["kind"], "name": comp["name"],
        "entity_type": "country", "official_owner": None, "summary": comp["summary"],
        "topics": comp.get("topics", []), "output_licence": "CC BY 4.0",
        "definition": {
            "normalisation": comp["normalisation"], "aggregation": comp["aggregation"],
            "min_coverage": comp["min_coverage"], "reference_year": ref, "max_data_age": age,
            "eligibility": comp.get("eligibility", {}), "mc": mc,
            "pillars": [{"id": p["id"], "name": p["name"], "weight": p["weight"],
                         "indicators": [{"id": i["id"], "weight": i["weight"],
                                         "direction": model.indicators[i["id"]]["direction"],
                                         "transform": model.indicators[i["id"]].get("transform")}
                                        for i in p["indicators"]]} for p in comp["pillars"]],
        },
        "results": rows, "ranked_count": len(ranked), "excluded_count": len(rows) - len(ranked),
        "sensitivity_note": f"{stable} of the top 10 stay in the top 10 in at least 95% of {mc['runs']:,} weight perturbations (±{int(mc['spread']*100)}%).",
        "top10": top10, "unit": "score (0–100)", "decimals": 1, "order": "desc",
    }


def _vals_cache(model, e, ind, used_years):
    y = used_years[ind][e]
    for yy, v, _ in model.series(e, ind):
        if yy == y:
            return v
    return None


def build_hdi(model: Model, cfg: dict, hdr_rank: dict) -> dict:
    year = cfg["year"]
    rows, diffs = [], []
    countries = [c["entity_id"] for c in model.countries()]
    vals = {}
    for e in countries:
        v = model.latest(e, "hdi", max_year=year, min_year=year)
        if v:
            vals[e] = v[1]
    prev = {e: model.latest(e, "hdi", max_year=year - 1, min_year=year - 1) for e in vals}
    prev_sorted = sorted((p[1] for p in prev.values() if p), reverse=True)

    def rank_in(sorted_desc, v):
        return 1 + sum(1 for x in sorted_desc if x > v)

    for e in countries:
        if e not in vals:
            rows.append({"entity_id": e, "rank": None, "is_tied": False, "score": None, "coverage": 0.0,
                         "excluded_reason": "not_in_hdr", "pillar_scores": {}, "rank_low": None,
                         "rank_high": None, "movement": None})
            continue
        comps = {k: model.latest(e, k2, max_year=year, min_year=year)
                 for k, k2 in (("le", "life-expectancy-hdr"), ("eys", "expected-schooling"),
                               ("mys", "mean-schooling"), ("gnipc", "gni-per-capita"))}
        mine = None
        if all(comps.values()):
            mine = engine.hdi(*(comps[k][1] for k in ("le", "eys", "mys", "gnipc")))
            diffs.append((e, round(mine, 3) - round(vals[e], 3), mine, vals[e]))
        p = prev.get(e)
        movement = (rank_in(prev_sorted, p[1]) - hdr_rank[e]) if p and e in hdr_rank else None
        rows.append({"entity_id": e, "rank": hdr_rank.get(e), "is_tied": False, "score": vals[e],
                     "coverage": 1.0, "excluded_reason": None, "pillar_scores": {}, "rank_low": None,
                     "rank_high": None, "movement": movement,
                     "recomputed": None if mine is None else round(mine, 4)})
    ranked = [r for r in rows if r["rank"]]
    counts = {}
    for r in ranked:
        counts[r["rank"]] = counts.get(r["rank"], 0) + 1
    for r in ranked:
        r["is_tied"] = counts[r["rank"]] > 1
    ranked.sort(key=lambda r: (r["rank"], r["entity_id"]))
    rows = ranked + [r for r in rows if not r["rank"]]
    exact = sum(1 for d in diffs if abs(d[1]) < 1e-9)
    model.hdi_check = {"compared": len(diffs), "exact_to_3dp": exact,
                       "share": round(exact / len(diffs), 4) if diffs else 0,
                       "max_abs_diff": round(max((abs(d[2] - d[3]) for d in diffs), default=0), 4),
                       "mismatches": [{"entity_id": d[0], "recomputed": round(d[2], 4), "published": d[3]}
                                      for d in diffs if abs(d[1]) >= 1e-9]}
    return {
        "ranking_id": cfg["id"], "version": cfg["version"], "kind": cfg["kind"], "name": cfg["name"],
        "entity_type": "country", "official_owner": cfg["official_owner"], "summary": cfg["summary"],
        "topics": cfg.get("topics", []), "output_licence": "CC BY 3.0 IGO (UNDP)",
        "definition": {"indicator": "hdi", "year": year, "goalposts": engine.HDI_GOALPOSTS,
                       "aggregation": "geometric mean of health, education and income indices"},
        "results": rows, "ranked_count": len(ranked), "excluded_count": len(rows) - len(ranked),
        "unit": "index (0–1)", "decimals": 3, "order": "desc", "top10": [r["entity_id"] for r in ranked[:10]],
    }


def build_official_published(model: Model, cfg: dict, official_rank: dict) -> dict:
    """An official index shown as published (not recomputed). Uses the owner's ranks where it
    publishes them; otherwise ranks by value and says so (ranks_by='this site')."""
    year, ind = cfg["year"], model.indicators[cfg["indicator"]]
    desc = cfg.get("order", "desc") == "desc"
    countries = [c["entity_id"] for c in model.countries()]
    vals = {e: v[1] for e in countries if (v := model.latest(e, ind["id"], max_year=year, min_year=year))}
    res = engine.assign_ranks([engine.Result(e, v, coverage=1.0) for e, v in vals.items()], descending=desc)
    own = {r.entity_id: (r.rank, r.is_tied) for r in res}
    use_official = bool(official_rank)
    rows = []
    for e in countries:
        if e not in vals:
            rows.append({"entity_id": e, "rank": None, "is_tied": False, "score": None, "coverage": 0.0,
                         "excluded_reason": "not_in_hdr", "pillar_scores": {}, "rank_low": None,
                         "rank_high": None, "movement": None})
            continue
        rank = official_rank.get(e) if use_official else own[e][0]
        rows.append({"entity_id": e, "rank": rank, "is_tied": False if use_official else own[e][1],
                     "score": vals[e], "coverage": 1.0, "excluded_reason": None if rank else "not_ranked_by_owner",
                     "pillar_scores": {}, "rank_low": None, "rank_high": None, "movement": None})
    ranked = sorted((r for r in rows if r["rank"]), key=lambda r: (r["rank"], r["entity_id"]))
    if use_official:
        counts = {}
        for r in ranked:
            counts[r["rank"]] = counts.get(r["rank"], 0) + 1
        for r in ranked:
            r["is_tied"] = counts[r["rank"]] > 1
    rows = ranked + [r for r in rows if not r["rank"]]
    return {
        "ranking_id": cfg["id"], "version": cfg["version"], "kind": "official_reproduction", "name": cfg["name"],
        "entity_type": "country", "official_owner": cfg["official_owner"], "summary": cfg["summary"],
        "topics": cfg.get("topics", []), "output_licence": "CC BY 3.0 IGO (UNDP)", "indicator": ind["id"],
        "definition": {"indicator": ind["id"], "year": year, "order": cfg.get("order", "desc"),
                       "ranks_by": cfg["official_owner"] if use_official else "this site (from published values)"},
        "results": rows, "ranked_count": len(ranked), "excluded_count": len(rows) - len(ranked),
        "unit": ind["unit"], "decimals": ind.get("decimals", 3), "order": cfg.get("order", "desc"),
        "top10": [r["entity_id"] for r in ranked[:10]],
    }


def build_single(model: Model, cfg: dict, defaults: dict) -> dict:
    ref = cfg.get("reference_year", defaults["reference_year"])
    age = cfg.get("max_data_age", defaults["max_data_age"])
    ind = model.indicators[cfg["indicator"]]
    countries = [c["entity_id"] for c in model.countries()]
    vals, years = _window_values(model, ind["id"], countries, ref, age)
    res = [engine.Result(e, v, coverage=1.0) for e, v in vals.items()]
    res = engine.assign_ranks(res, descending=cfg["order"] == "desc")
    rows = [{"entity_id": r.entity_id, "rank": r.rank, "is_tied": r.is_tied, "score": r.score,
             "year": years[r.entity_id], "coverage": 1.0, "excluded_reason": None, "pillar_scores": {},
             "rank_low": None, "rank_high": None, "movement": None} for r in res]
    for e in sorted(set(countries) - set(vals)):
        rows.append({"entity_id": e, "rank": None, "is_tied": False, "score": None, "year": None,
                     "coverage": 0.0, "excluded_reason": "no_recent_data", "pillar_scores": {},
                     "rank_low": None, "rank_high": None, "movement": None})
    return {
        "ranking_id": cfg["id"], "version": defaults["version"], "kind": "single_indicator", "name": cfg["name"],
        "entity_type": "country", "official_owner": None, "indicator": ind["id"],
        "columns": cfg.get("columns", []), "value_label": cfg.get("value_label"),
        "summary": f"{ind['definition']} Countries ranked by their latest value from {ref - age} to {ref}.",
        "topics": cfg.get("topics", []), "output_licence": model.sources[ind["source"]]["licence"],
        "definition": {"indicator": ind["id"], "order": cfg["order"], "reference_year": ref, "max_data_age": age},
        "results": rows, "ranked_count": len(vals), "excluded_count": len(rows) - len(vals),
        "unit": ind["unit"], "decimals": ind.get("decimals", 2), "order": cfg["order"],
        "top10": [r["entity_id"] for r in rows[:10] if r["rank"]],
    }


# ----------------------------------------------------------------------------- derived
def percentiles(model: Model) -> dict[tuple[str, str], float]:
    """Share of countries (latest value, last 6 years) this entity beats, direction-aware."""
    out = {}
    countries = [c["entity_id"] for c in model.countries()]
    for ind_id, ind in model.indicators.items():
        vals = {}
        for e in countries:
            lt = model.latest(e, ind_id, min_year=YEAR_MAX - 7)
            if lt:
                vals[e] = lt[1]
        if len(vals) < 10:
            continue
        xs = sorted(vals.values())
        n = len(xs)
        for e, v in vals.items():
            below = bisect_left(xs, v)
            above = n - bisect_right(xs, v)
            # share of other countries this one is better than (or higher than, if neutral)
            p = above / (n - 1) if ind["direction"] == "lower_better" else below / (n - 1)
            out[(e, ind_id)] = round(100 * p)
    return out


# ----------------------------------------------------------------------------- export
def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str),
                    encoding="utf-8")


def _value(model: Model, e: str, ind_id: str, y: int, v: float, s: str) -> dict:
    ind = model.indicators[ind_id]
    src = model.sources[ind["source"]]
    return {"kind": "observed", "value": v, "year": y, "status": s, "source": ind["source"],
            "source_licence": src["licence"], "source_url": src["url"],
            "retrieved_at": ind["_retrieved_at"], "modified": False}


def export(model: Model, pct: dict) -> Path:
    rel_dir = DIST / "v1" / "releases" / model.release
    if rel_dir.exists():
        shutil.rmtree(rel_dir)
    rel_dir.mkdir(parents=True)

    # sources / indicators / rankings index
    used_sources = sorted({i["source"] for i in model.indicators.values()} | {"natural-earth", "wikidata", "cliopatria", "maddison", "ucdp"})
    _dump(rel_dir / "sources.json", [{k: model.sources[s].get(k) for k in
          ("source_id", "publisher", "title", "url", "licence", "licence_url", "attribution_text",
           "share_alike", "no_modification", "licence_checked_on")} for s in used_sources])
    ind_public = [{
        "indicator_id": i["id"], "name": i["name"], "definition": i["definition"], "unit": i["unit"],
        "direction": i["direction"], "dimension": i["dimension"], "applies_to": ["country"],
        "source": i["source"], "source_code": i["code"], "source_licence": model.sources[i["source"]]["licence"],
        "display_only": i.get("display_only", False), "decimals": i.get("decimals", 2),
        "transform": i.get("transform"),
    } for i in model.indicators.values()]
    _dump(rel_dir / "indicators.json", ind_public)
    _dump(rel_dir / "rankings.json", [{
        "ranking_id": r["ranking_id"], "name": r["name"], "kind": r["kind"], "entity_type": "country",
        "official_owner": r["official_owner"], "current_version": r["version"], "versions": [r["version"]],
        "output_licence": r["output_licence"]} for r in model.rankings.values()])

    # entities
    country_ids = [c["entity_id"] for c in model.countries()]
    _dump(rel_dir / "entities" / "country.json",
          [{k: c.get(k) for k in ("entity_id", "type", "slug", "name", "iso3")} for c in model.countries()])
    _dump(rel_dir / "entities" / "country_group.json",
          [{k: e.get(k) for k in ("entity_id", "type", "slug", "name", "iso3")}
           for e in model.entities.values() if e["type"] == "country_group"])
    positions = {e: [] for e in country_ids}
    for r in model.rankings.values():
        for row in r["results"]:
            positions[row["entity_id"]].append({
                "ranking_id": r["ranking_id"], "version": r["version"], "rank": row["rank"],
                "is_tied": row["is_tied"], "of": r["ranked_count"], "rank_low": row["rank_low"],
                "rank_high": row["rank_high"], "movement": row["movement"],
                "excluded_reason": row["excluded_reason"]})
    for c in model.countries():
        e = c["entity_id"]
        latest, series = {}, {}
        for ind_id in model.indicators:
            ser = model.series(e, ind_id)
            if not ser:
                continue
            y, v, s = ser[-1]
            latest[ind_id] = _value(model, e, ind_id, y, v, s)
            series[ind_id] = [[yy, vv] for yy, vv, _ in ser]
        _dump(rel_dir / "entities" / "country" / f"{e}.json", {
            **{k: c.get(k) for k in ("entity_id", "type", "slug", "name", "iso3")},
            "groups": [{"entity_id": g, "name": model.entities[g]["name"], "slug": model.entities[g]["slug"]}
                       for g in (c["region_id"], c["income_id"]) if g],
            "attributes": {k: c.get(k) for k in ("region", "income", "capital", "lat", "lon", "iso2")},
            "facts": model.facts.get(e, {}),
            "latest": latest, "series": series,
            "percentiles": {ind: pct[(e, ind)] for ind in model.indicators if (e, ind) in pct},
            "rankings": positions[e], "summary": None,
        })

    world = {}
    for ind_id in model.indicators:
        ser = model.series("WLD", ind_id)
        if ser:
            world[ind_id] = {"latest": _value(model, "WLD", ind_id, *ser[-1]), "series": [[y, v] for y, v, _ in ser]}
    _dump(rel_dir / "entities" / "world.json", {"entity_id": "WLD", "name": "World", "indicators": world})

    # indicators (full data)
    for ind_id, ind in model.indicators.items():
        data, cov = {}, {}
        for e in country_ids:
            ser = model.series(e, ind_id)
            if ser:
                data[e] = [[y, v, s] for y, v, s in ser]
                for y, _, _ in ser:
                    cov[str(y)] = cov.get(str(y), 0) + 1
        pub = next(p for p in ind_public if p["indicator_id"] == ind_id)
        _dump(rel_dir / "indicators" / f"{ind_id}.json", {**pub, "coverage_by_year": cov, "data": data,
                                                          "world": [[y, v, s] for y, v, s in model.series("WLD", ind_id)],
                                                          "retrieved_at": ind["_retrieved_at"]})

    # rankings
    for r in model.rankings.values():
        _dump(rel_dir / "rankings" / r["ranking_id"] / f"{r['version']}.json", {
            "definition": {"ranking_id": r["ranking_id"], "version": r["version"], "kind": r["kind"],
                           "name": r["name"], "official_owner": r["official_owner"],
                           "output_licence": r["output_licence"], **r["definition"],
                           "methodology_url": f"/methodology/{r['ranking_id']}/"},
            "results": [{k: v for k, v in row.items() if k != "indicator_values"} for row in r["results"]],
        })

    # matrix for the Index Builder: only indicators allowed as engine inputs
    matrix_inds = [i for i in ind_public if not i["display_only"] and i["source"] != "gdelt"
                   and not model.sources[i["source"]]["share_alike"]
                   and not model.sources[i["source"]].get("no_modification")]
    values, years = [], []
    for e in country_ids:
        vr, yr = [], []
        for i in matrix_inds:
            lt = model.latest(e, i["indicator_id"], max_year=REF_YEAR, min_year=REF_YEAR - REF_AGE)
            vr.append(lt[1] if lt else None)
            yr.append(lt[0] if lt else None)
        values.append(vr)
        years.append(yr)
    pop = {e: (model.latest(e, "population") or (None, None))[1] for e in country_ids}
    _dump(rel_dir / "matrix.json", {
        "release": model.release, "entities": country_ids,
        "names": [model.entities[e]["name"] for e in country_ids],
        "slugs": [model.entities[e]["slug"] for e in country_ids],
        "iso2": [model.entities[e]["iso2"] for e in country_ids],
        "regions": [model.entities[e]["region"] for e in country_ids],
        "population": [pop[e] for e in country_ids],
        "indicators": matrix_inds, "values": values, "years": years,
        "reference_year": REF_YEAR, "max_data_age": REF_AGE,
    })

    # bulk tables via DuckDB → CSV + Parquet
    bulk = rel_dir / "bulk"
    bulk.mkdir()
    BUILD.mkdir(exist_ok=True)
    obs_path = BUILD / "observations.ndjson"
    with open(obs_path, "w", encoding="utf-8") as f:
        for (e, ind_id), ser in sorted(model.obs.items()):
            ind = model.indicators[ind_id]
            src = model.sources[ind["source"]]
            for y, v, s in ser:
                f.write(json.dumps({"entity_id": e, "indicator_id": ind_id, "year": y, "value": v, "status": s,
                                    "source": ind["source"], "source_licence": src["licence"],
                                    "source_url": src["url"], "retrieved_at": ind["_retrieved_at"],
                                    "modified": False}) + "\n")
    tables = {
        "observations": obs_path,
        "entities": [{k: c.get(k) for k in ("entity_id", "type", "slug", "name", "iso3", "region", "income", "capital")}
                     for c in model.countries()],
        "indicators": ind_public,
        "sources": json.loads((rel_dir / "sources.json").read_text(encoding="utf-8")),
        "ranking_results": [{"ranking_id": r["ranking_id"], "version": r["version"], "entity_id": row["entity_id"],
                             "rank": row["rank"], "is_tied": row["is_tied"], "score": row["score"],
                             "rank_low": row["rank_low"], "rank_high": row["rank_high"],
                             "coverage": row["coverage"], "excluded_reason": row["excluded_reason"]}
                            for r in model.rankings.values() for row in r["results"]],
    }
    con = duckdb.connect()
    for name, src in tables.items():
        p = src if isinstance(src, Path) else BUILD / f"{name}.ndjson"
        if not isinstance(src, Path):
            with open(p, "w", encoding="utf-8") as f:
                for row in src:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        q = f"SELECT * FROM read_json_auto('{p.as_posix()}', format='newline_delimited')"
        # gzip keeps every file under Cloudflare's 25 MiB static-asset limit
        con.execute(f"COPY ({q}) TO '{(bulk / (name + '.csv.gz')).as_posix()}' (HEADER, COMPRESSION gzip)")
        con.execute(f"COPY ({q}) TO '{(bulk / (name + '.parquet')).as_posix()}' (FORMAT parquet)")

    attribution = "\n".join(f"- **{model.sources[s]['publisher']}** — {model.sources[s]['title']}. "
                            f"{model.sources[s]['attribution_text']} <{model.sources[s]['url']}>"
                            for s in used_sources)
    (rel_dir / "ATTRIBUTION.md").write_text(
        f"# Attribution — release {model.release}\n\nThis release contains data from:\n\n{attribution}\n\n"
        "Rankings and composite scores calculated by the platform are licensed under CC BY 4.0.\n"
        "Source values keep the licence of their source (column `source_licence`).\n", encoding="utf-8")
    (rel_dir / "LICENSE.txt").write_text(
        "Data in this release: Creative Commons Attribution 4.0 International (CC BY 4.0),\n"
        "https://creativecommons.org/licenses/by/4.0/ — except where a row's `source_licence`\n"
        "says otherwise (UNDP HDR values: CC BY 3.0 IGO). See ATTRIBUTION.md.\n", encoding="utf-8")

    files = []
    for p in sorted(rel_dir.rglob("*")):
        if p.is_file():
            b = p.read_bytes()
            files.append({"path": p.relative_to(rel_dir).as_posix(), "bytes": len(b),
                          "sha256": hashlib.sha256(b).hexdigest()})
    _dump(rel_dir / "manifest.json", {"release": model.release, "engine_version": _git_sha(),
                                      "source_releases": sorted(model.source_releases.values(),
                                                                key=lambda r: r["source_release_id"]),
                                      "files": files})
    latest = DIST / "v1" / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(rel_dir, latest)
    releases = sorted((p.name for p in (DIST / "v1" / "releases").iterdir() if p.is_dir()), reverse=True)
    _dump(DIST / "v1" / "releases.json", [{"release": r, "path": f"releases/{r}",
                                           "notes_url": f"/insights/releases/{r}/"} for r in releases])
    return rel_dir


def _git_sha() -> str:
    head = Path(__file__).resolve().parent.parent / ".git" / "HEAD"
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            return (head.parent / ref[5:]).read_text().strip()[:12]
        return ref[:12]
    except OSError:
        return "uncommitted"


# ----------------------------------------------------------------------------- main
def build(strict: bool = False) -> Model:
    release = RELEASE or date.today().isoformat()
    cat = load_yaml("indicators.yaml")
    lic = load_yaml("licences.yaml")
    rcfg = load_yaml("rankings.yaml")
    sources = {s["source_id"]: s for s in lic["sources"]}
    for ind in cat["indicators"]:
        if ind["source"] not in sources:
            raise GateError(f"indicator {ind['id']} uses unknown source {ind['source']}")
    print("Loading entities")
    entities, groups = load_entities()
    print(f"  {sum(1 for e in entities.values() if e['type']=='country')} countries, {len(groups)} groups")
    print("Loading observations")
    pre_warnings: list[str] = []
    check_series_licences(cat, pre_warnings)
    for w in pre_warnings:
        print(f"  {w}")
    obs, rejects, srel, hdr_rank = load_observations(cat, entities, sources)
    print(f"  {sum(len(v) for v in obs.values()):,} observations, {len(rejects)} rejected")
    model = Model(release=release, sources=sources, source_releases=srel, dimensions=cat["dimensions"],
                  indicators={i["id"]: i for i in cat["indicators"]}, entities=entities, groups=groups,
                  obs=obs, rejects=rejects, warnings=pre_warnings, facts=facts.load(entities))
    for ind in model.indicators.values():
        if not any(k[1] == ind["id"] for k in obs):
            raise GateError(f"indicator {ind['id']} has no data after validation")
    print("Licence gate")
    licence_gate(model, rcfg, strict, Path(__file__).with_name("schema.sql"))
    print("Rankings")
    for comp in rcfg["composites"]:
        model.rankings[comp["id"]] = build_composite(model, comp)
    for off in rcfg["official"]:
        if off.get("method") == "published":
            model.rankings[off["id"]] = build_official_published(model, off, hdr_rank.get(off["indicator"], {}))
        else:
            model.rankings[off["id"]] = build_hdi(model, off, hdr_rank["hdi"])
    for s in rcfg["single"]:
        model.rankings[s["id"]] = build_single(model, s, rcfg["single_defaults"])
    for r in model.rankings.values():
        print(f"  {r['ranking_id']:<24} {r['ranked_count']:>4} ranked, {r['excluded_count']:>4} not ranked")
    hc = model.hdi_check
    print(f"  HDI check: {hc['exact_to_3dp']}/{hc['compared']} match UNDP to 3 dp (max diff {hc['max_abs_diff']})")
    if hc["compared"] and hc["share"] < 0.95:
        raise GateError(f"HDI reproduction below 95%: {hc['share']:.1%}")
    print("Exporting release")
    pct = percentiles(model)
    out = export(model, pct)
    n = sum(1 for p in out.rglob("*") if p.is_file())
    print(f"  {n} files in {out.relative_to(DIST.parent)}")
    for w in model.warnings:
        print(f"  WARNING: {w}", file=sys.stderr)
    return model
