"""Beyond countries: universities (OpenAlex, CC0) and cities (GHSL Urban Centre Database, CC BY 4.0).

Both are lists of places inside countries, so they get their own pages and a section on each
country page rather than entering the country indicators, rankings or composite indices.
"""
from __future__ import annotations

import csv
import io
import json
import unicodedata
import zipfile

from .config import RAW

CITY_MIN_POP = 1_000_000        # urban centres listed on /cities/
CITY_YEARS = list(range(1975, 2031, 5))

# GHSL country names (from GADM) that differ from this site's names or aliases
GADM_FIX = {
    "Côte d'Ivoire": "CIV", "Democratic Republic of the Congo": "COD", "Republic of the Congo": "COG",
    "Congo": "COG", "Myanmar": "MMR", "Russia": "RUS", "Syria": "SYR", "Iran": "IRN", "Laos": "LAO",
    "Vietnam": "VNM", "South Korea": "KOR", "North Korea": "PRK", "Turkey": "TUR", "Türkiye": "TUR",
    "Czech Republic": "CZE", "Czechia": "CZE", "Macedonia": "MKD", "North Macedonia": "MKD",
    "Palestine": "PSE", "Swaziland": "SWZ", "Eswatini": "SWZ", "Cape Verde": "CPV", "Timor-Leste": "TLS",
    "East Timor": "TLS", "Gambia": "GMB", "The Gambia": "GMB", "Bahamas": "BHS", "Brunei": "BRN",
    "Micronesia": "FSM", "Kyrgyzstan": "KGZ", "Slovakia": "SVK", "Egypt": "EGY", "Yemen": "YEM",
    "Venezuela": "VEN", "Hong Kong": "HKG", "Macao": "MAC", "Taiwan": None, "Kosovo": "XKX",
    "São Tomé and Príncipe": "STP", "Sao Tome and Principe": "STP", "Saint Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA", "Saint Vincent and the Grenadines": "VCT", "Puerto Rico": "PRI",
    "United States": "USA", "United Kingdom": "GBR", "Tanzania": "TZA", "Bolivia": "BOL", "Moldova": "MDA",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().casefold()
    return "".join(ch for ch in s if ch.isalnum())


def _zip_csv(path, suffix: str) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(suffix))
        with z.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace")))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_universities(model) -> list[dict]:
    path = RAW / "openalex" / "institutions.json"
    if not path.exists():
        return []
    iso2 = {(e.get("iso2") or "").upper(): eid for eid, e in model.entities.items() if e["type"] == "country"}
    iso2["XK"] = iso2.get("XK") or ("XKX" if "XKX" in model.entities else None)
    out = []
    for r in json.loads(path.read_text(encoding="utf-8"))["results"]:
        s = r.get("summary_stats") or {}
        out.append({"id": r["id"].rsplit("/", 1)[-1], "name": r["display_name"], "cc": (r.get("country_code") or "").upper(),
                    "iso3": iso2.get((r.get("country_code") or "").upper()),
                    "city": (r.get("geo") or {}).get("city"), "works": r.get("works_count") or 0,
                    "cites": r.get("cited_by_count") or 0, "h": s.get("h_index"), "i10": s.get("i10_index"),
                    "mean2": s.get("2yr_mean_citedness"), "url": r.get("homepage_url"), "ror": r.get("ror")})
    out.sort(key=lambda u: -u["cites"])
    for i, u in enumerate(out, 1):
        u["rank"] = i
    return out


def load_cities(model) -> tuple[list[dict], list[str]]:
    gc_path, gh_path = RAW / "ghsl" / "GENERAL_CHARACTERISTICS.zip", RAW / "ghsl" / "GHSL.zip"
    if not (gc_path.exists() and gh_path.exists()):
        return [], []
    lookup = {}
    for eid, e in model.entities.items():
        if e["type"] != "country":
            continue
        for n in [e["name"], e.get("source_name"), *(e.get("aliases") or [])]:
            if n:
                lookup[_norm(n)] = eid
    for k, v in GADM_FIX.items():
        lookup[_norm(k)] = v
    pops = {r["ID_UC_G0"]: r for r in _zip_csv(gh_path, ".csv")}
    out, unmatched = [], set()
    for r in _zip_csv(gc_path, ".csv"):
        p = pops.get(r["ID_UC_G0"], {})
        series = [(y, _num(p.get(f"GH_POP_TOT_{y}"))) for y in CITY_YEARS]
        series = [(y, v) for y, v in series if v is not None]
        now = dict(series).get(2025) or _num(r.get("GC_POP_TOT_2025"))
        if not now or now < CITY_MIN_POP:
            continue
        country = r.get("GC_CNT_GAD_2025") or ""
        iso3 = lookup.get(_norm(country))
        if iso3 is None and _norm(country) not in lookup:
            unmatched.add(country)
        area = _num(r.get("GC_UCA_KM2_2025"))
        s = dict(series)
        out.append({"id": r["ID_UC_G0"], "name": r.get("GC_UCN_MAI_2025") or "Unnamed", "also": r.get("GC_UCN_LIS_2025") or "",
                    "country": country, "iso3": iso3, "people": now, "pop1975": s.get(1975), "pop2030": s.get(2030),
                    "area": area, "density": now / area if area else None, "series": series,
                    "capital": (r.get("GC_UCM_CAP") or "").strip() not in ("", "0", "No", "no")})
    out.sort(key=lambda c: -c["people"])
    for i, c in enumerate(out, 1):
        c["rank"] = i
    return out, sorted(unmatched)
