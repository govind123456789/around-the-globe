"""Stage 1: download raw source files into raw/ with checksums.

Every download is cached. Pass --refresh to re-download. Each raw file gets a
sidecar <file>.meta.json with url, retrieved_at and sha256 so a release can
record exactly what it was built from.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .config import RAW, load_yaml

WB_API = "https://api.worldbank.org/v2"
HDR_URL = "https://hdr.undp.org/sites/default/files/2025_HDR/HDR25_Composite_indices_complete_time_series.csv"
# Natural Earth "point of view" edition showing boundaries as India officially depicts them.
# Only published at 1:10m, so it is simplified for the web with mapshaper (Node).
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries_ind.geojson"
MAPSHAPER = "mapshaper@0.7.93"
# transparency.org downloads are often unreachable; Our World in Data republishes the
# same CPI series (2012 onward) with attribution to Transparency International.
CPI_URL = "https://ourworldindata.org/grapher/ti-corruption-perception-index.csv?v=1&csvType=full&useColumnShortNames=true"
WPP_URL = "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_Demographic_Indicators_Medium.csv.gz"
EMBER_URL = "https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_yearly_global.csv"
GHSL_BASE = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/GHS_UCDB_THEME_GLOBE_R2024A"
OPENALEX = "https://api.openalex.org/institutions"
OECD_API = "https://sdmx.oecd.org/public/rest/data"
GDELT_EVENTS = "https://data.gdeltproject.org/events"     # GDELT 1.0 daily event exports
GDELT_DAYS, GDELT_STEP = 90, 3                             # every 3rd day over the last 90 days
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Historical layer
CLIOPATRIA_URL = "https://raw.githubusercontent.com/Seshat-Global-History-Databank/cliopatria/main/cliopatria.geojson.zip"
MADDISON_URL = "https://dataverse.nl/api/access/datafile/421302"        # mpd2023_web.xlsx, doi:10.34894/INZBF2
UCDP_URLS = {"acd": "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-261-csv.zip",
             "brd": "https://ucdp.uu.se/downloads/brd/ucdp-brd-conf-261-csv.zip"}
# Wars, revolutions, coups and rebellions since 200 BCE, located (directly, via "present-day
# location" or via their location) in a country that has an ISO 3166 alpha-3 code.
WIKIDATA_EVENTS_QUERY = """
SELECT ?ev ?evLabel ?start ?end ?iso3 ?deaths ?article WHERE {
  ?ev wdt:P31/wdt:P279* wd:%s .
  { ?ev wdt:P580 ?start } UNION { ?ev wdt:P585 ?start }
  OPTIONAL { ?ev wdt:P582 ?end }
  { ?ev wdt:P17 ?c } UNION { ?ev wdt:P3842/wdt:P17 ?c } UNION { ?ev wdt:P276/wdt:P17 ?c }
  ?c wdt:P298 ?iso3 .
  OPTIONAL { ?ev wdt:P1120 ?deaths }
  OPTIONAL { ?article schema:about ?ev ; schema:isPartOf <https://en.wikipedia.org/> }
  FILTER(YEAR(?start) >= -200)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""
EVENT_TYPES = {"Q198": "war", "Q10931": "revolution", "Q45382": "coup", "Q124734": "rebellion"}

session = requests.Session()
session.headers["User-Agent"] = "around-the-globe-pipeline/0.1 (+open data rankings)"


def _get(url: str, params: dict | None = None, attempts: int = 5) -> requests.Response:
    for i in range(attempts):
        try:
            r = session.get(url, params=params, timeout=90)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} for {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  {type(e).__name__} for {url}", file=sys.stderr)
        time.sleep(2 ** i)
    raise RuntimeError(f"failed after {attempts} attempts: {url}")


def _write(path: Path, content: bytes, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    meta = {
        "url": url,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }
    path.with_suffix(path.suffix + ".meta.json").write_text(json.dumps(meta, indent=2))


def fetch_wb_countries(refresh: bool) -> None:
    out = RAW / "wb" / "countries.json"
    if out.exists() and not refresh:
        return
    url = f"{WB_API}/country"
    r = _get(url, {"format": "json", "per_page": 400})
    _write(out, r.content, r.url)
    print(f"  countries: {len(r.json()[1])}")


WB_SOURCE_ID = {"wb-wdi": 2, "wb-wgi": 3}     # World Bank API source ids


def fetch_wb_licence(code: str, source: str, refresh: bool) -> None:
    """Per-series licence from the World Bank metadata API. A few WDI series carry a licence
    other than CC BY 4.0; build_data excludes those."""
    out = RAW / "wb" / "licence" / f"{code}.json"
    if out.exists() and not refresh:
        return
    url = f"{WB_API}/sources/{WB_SOURCE_ID[source]}/series/{code}/metadata"
    for attempt in range(6):
        try:
            d = _get(url, {"format": "json"}, attempts=2).json()
            vals = {m["id"]: m["value"] for v in d["source"][0]["concept"][0]["variable"] for m in v["metatype"]}
            break
        except (RuntimeError, KeyError, IndexError, ValueError):
            time.sleep(10 * (attempt + 1))         # the metadata API rate-limits bursts
    else:
        # The metadata API sometimes rate-limits for minutes. Keep the licence already on file; with none on
        # file the series is left out by the licence gate (check_series_licences), so nothing unchecked is published.
        print(f"  {code}: licence metadata unavailable, {'keeping the stored licence' if out.exists() else 'series will be excluded'}",
              file=sys.stderr)
        return
    rec = {k: vals.get(k) for k in ("License_Type", "License_URL", "Source")}
    _write(out, json.dumps(rec).encode(), url)


def fetch_wb_indicator(code: str, refresh: bool, source: str = "wb-wdi") -> None:
    fetch_wb_licence(code, source, refresh)
    out = RAW / "wb" / f"{code}.json"
    if out.exists() and not refresh:
        return
    url = f"{WB_API}/country/all/indicator/{code}"
    params = {"format": "json", "per_page": 20000, "date": "1990:2026", "source": WB_SOURCE_ID[source]}
    try:
        r = _get(url, params)
    except RuntimeError:
        if out.exists():                      # a short World Bank outage keeps last week's copy instead of failing the build
            print(f"  {code}: World Bank API unavailable, keeping the stored copy", file=sys.stderr)
            return
        raise
    body = r.json()
    if not isinstance(body, list) or len(body) < 2 or body[1] is None:
        raise RuntimeError(f"unexpected World Bank response for {code}: {str(body)[:200]}")
    pages = body[0].get("pages", 1)
    rows = body[1]
    for page in range(2, pages + 1):
        rows += _get(url, {**params, "page": page}).json()[1]
    meta_resp = _get(f"{WB_API}/indicator/{code}", {"format": "json"}).json()
    payload = {"indicator_meta": meta_resp[1][0] if len(meta_resp) > 1 else None, "rows": rows}
    _write(out, json.dumps(payload).encode(), r.url)
    print(f"  {code}: {len(rows)} rows")


def fetch_file(url: str, out: Path, refresh: bool) -> None:
    if out.exists() and not refresh:
        return
    r = _get(url)
    _write(out, r.content, url)
    print(f"  {out.name}: {len(r.content):,} bytes")


def fetch_openalex(refresh: bool, limit: int = 2000) -> None:
    """The most-cited educational institutions, with summary statistics. Keyless OpenAlex access
    has a small shared daily budget, so this runs only when the cached file is missing or --refresh."""
    out = RAW / "openalex" / "institutions.json"
    if out.exists() and not refresh:
        return
    fields = "id,ror,display_name,country_code,works_count,cited_by_count,summary_stats,homepage_url,geo"
    key = os.environ.get("OPENALEX_API_KEY", "").strip()   # optional; set as a secret, never in the repo
    results = []                     # numbered pages work with or without a key
    for page in range(1, limit // 200 + 1):
        params = {"filter": "type:education", "sort": "cited_by_count:desc", "per-page": 200, "select": fields, "page": page}
        if key:
            params["api_key"] = key
        d = _get(OPENALEX, params).json()
        results += d["results"]
        if len(d["results"]) < 200:
            break
    body = json.dumps({"query": "type:education sorted by cited_by_count", "results": results[:limit]}, ensure_ascii=False)
    _write(out, body.encode("utf-8"), OPENALEX)
    print(f"  {len(results[:limit])} institutions")


def fetch_oecd(ind: dict, refresh: bool) -> None:
    """ind['code'] is 'AGENCY,DATAFLOW,VERSION/KEY' for the OECD SDMX REST API."""
    out = RAW / "oecd" / f"{ind['id']}.csv"
    if out.exists() and not refresh:
        return
    url = f"{OECD_API}/{ind['code']}"
    r = _get(url, {"startPeriod": 1990, "format": "csvfile"})
    _write(out, r.content, r.url)
    rows = len(r.content.splitlines()) - 1
    print(f"  {ind['id']}: {rows} rows")


# Country facts from Wikidata, one query per fact. Items with a dissolution date are left out.
FACT_QUERIES = {
    "neighbours": "?c wdt:P47 ?v . ?v wdt:P298 ?extra . FILTER NOT EXISTS { ?v wdt:P576 ?vend }",
    "languages": "?c wdt:P37 ?v . OPTIONAL { ?v wdt:P218 ?extra }",
    "currency": "?c wdt:P38 ?v . OPTIONAL { ?v wdt:P498 ?extra }",
    "calling_code": "?c wdt:P474 ?v .",
    "internet_domain": "?c wdt:P78 ?v .",
    "drives_on": "?c wdt:P1622 ?v .",
    "time_zones": "?c wdt:P421 ?v .",
    # elevation normalised to metres: raw values can be in feet
    "highest_point": "?c wdt:P610 ?v . OPTIONAL { ?v p:P2044 ?st . ?st a wikibase:BestRank ; psn:P2044/wikibase:quantityAmount ?extra }",
    "government": "?c wdt:P122 ?v .",
}


def fetch_country_facts(refresh: bool) -> None:
    """One CSV per fact in raw/wikidata/facts/ (Wikidata is CC0)."""
    for name, clause in FACT_QUERIES.items():
        out = RAW / "wikidata" / "facts" / f"{name}.csv"
        if out.exists() and not refresh:
            continue
        q = ("SELECT ?iso3 ?c ?v ?vLabel ?extra WHERE { ?c wdt:P298 ?iso3 . FILTER NOT EXISTS { ?c wdt:P576 ?end } "
             + clause + ' SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }')
        for attempt in range(4):
            r = session.get(WIKIDATA_SPARQL, params={"query": q}, headers={"Accept": "text/csv"}, timeout=180)
            if r.status_code == 200:
                break
            time.sleep(15 * (attempt + 1))
        r.raise_for_status()
        _write(out, r.content, WIKIDATA_SPARQL)
        print(f"  facts/{name}: {len(r.content.splitlines()) - 1} rows")
        time.sleep(2)


def fetch_fips_map(refresh: bool) -> None:
    """GDELT uses FIPS 10-4 country codes; Wikidata (CC0) maps them to ISO 3166 alpha-3."""
    out = RAW / "wikidata" / "fips_iso3.csv"
    if out.exists() and not refresh:
        return
    q = "SELECT ?fips ?iso3 WHERE { ?c wdt:P901 ?fips; wdt:P298 ?iso3 }"
    r = session.get(WIKIDATA_SPARQL, params={"query": q}, headers={"Accept": "text/csv"}, timeout=120)
    r.raise_for_status()
    _write(out, r.content, WIKIDATA_SPARQL)
    print(f"  FIPS to ISO3 map: {len(r.content.splitlines()) - 1} rows")


def fetch_gdelt(refresh: bool, today: date | None = None) -> None:
    """Aggregate GDELT 1.0 daily event files into per-country news volume and tone.

    Samples every GDELT_STEP-th day over the last GDELT_DAYS days. Each daily zip
    (~7 MB) is reduced to a small JSON of per-FIPS-country totals and not kept;
    the zip's checksum is recorded in the JSON's .meta.json.
    """
    today = today or date.today()
    days = [today - timedelta(days=d) for d in range(1, GDELT_DAYS + 1, GDELT_STEP)]
    outdir = RAW / "gdelt" / "daily"
    todo = [d for d in days if refresh or not (outdir / f"{d:%Y%m%d}.json").exists()]
    if todo:
        print(f"  GDELT: {len(todo)} daily files to fetch (~{len(todo) * 7} MB)")
    csv.field_size_limit(10 ** 7)
    for d in todo:
        url = f"{GDELT_EVENTS}/{d:%Y%m%d}.export.CSV.zip"
        try:
            r = _get(url, attempts=3)
        except RuntimeError:
            print(f"    {d}: not available, skipped")
            continue
        totals: dict[str, list[float]] = {}
        all_articles = 0
        with zipfile.ZipFile(io.BytesIO(r.content)) as z, z.open(z.namelist()[0]) as f:
            for row in csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"), delimiter="\t"):
                if len(row) < 58:
                    continue
                n = int(row[33] or 0)          # NumArticles
                all_articles += n
                fips = row[51]                 # ActionGeo_CountryCode
                if fips and n:
                    t = totals.setdefault(fips, [0, 0.0])
                    t[0] += n
                    t[1] += n * float(row[34] or 0)   # AvgTone
        payload = {"date": d.isoformat(), "all_articles": all_articles,
                   "countries": {k: {"articles": v[0], "tone_x_articles": round(v[1], 4)}
                                 for k, v in sorted(totals.items())}}
        out = outdir / f"{d:%Y%m%d}.json"
        _write(out, json.dumps(payload).encode(), url)
        meta_path = out.with_suffix(".json.meta.json")
        meta = json.loads(meta_path.read_text())
        meta["source_zip_sha256"] = hashlib.sha256(r.content).hexdigest()
        meta_path.write_text(json.dumps(meta, indent=2))
        print(f"    {d}: {all_articles:,} articles, {len(totals)} countries")


# Geopolitics: UCDP event data (final to last year, plus this year's preliminary 'candidate' events),
# UN General Assembly voting (Voeten et al., CC0) and UNHCR refugee statistics (CC BY 4.0).
UCDP_GED_URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
UCDP_CANDIDATE_URL = "https://ucdp.uu.se/downloads/candidateged/GEDEvent_v26_01_26_09.csv"
UNVOTES_FILES = {"agreement.csv": 11837234, "idealpoints.csv": 14098429}     # Harvard Dataverse doi:10.7910/DVN/LEJUQZ
UNHCR_API = "https://api.unhcr.org/population/v1/population/"


def fetch_unhcr(name: str, params: dict, refresh: bool) -> None:
    out = RAW / "unhcr" / f"{name}.json"
    if out.exists() and not refresh:
        return
    rows, page = [], 1
    while True:
        d = _get(UNHCR_API, {**params, "limit": 10000, "page": page}).json()
        rows += d["items"]
        if page >= int(d.get("maxPages") or 1):
            break
        page += 1
    _write(out, json.dumps(rows).encode(), f"{UNHCR_API}?{'&'.join(f'{k}={v}' for k, v in params.items())}")
    print(f"  UNHCR {name}: {len(rows)} rows")


def fetch_geopolitics(refresh: bool) -> None:
    z = RAW / "ucdp" / "ged261-csv.zip"
    fetch_file(UCDP_GED_URL, z, refresh)
    fetch_file(UCDP_CANDIDATE_URL, RAW / "ucdp" / "candidate.csv", refresh)
    for name, fid in UNVOTES_FILES.items():
        fetch_file(f"https://dataverse.harvard.edu/api/access/datafile/{fid}", RAW / "unvotes" / name, refresh)
    fetch_unhcr("by_origin", {"yearFrom": 2000, "yearTo": 2025, "coo_all": "true"}, refresh)
    fetch_unhcr("by_asylum", {"yearFrom": 2000, "yearTo": 2025, "coa_all": "true"}, refresh)
    fetch_unhcr("flows", {"yearFrom": 2024, "yearTo": 2025, "coo_all": "true", "coa_all": "true"}, refresh)
    # US Treasury OFAC sanctions list (US government work, public domain)
    for f in ("SDN.CSV", "ADD.CSV"):
        fetch_file(f"https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/{f}", RAW / "ofac" / f.lower(), refresh)


def fetch_history(refresh: bool) -> None:
    """Sources for the historical timeline (Cliopatria, Maddison, Wikidata events, UCDP)."""
    out = RAW / "cliopatria" / "cliopatria.geojson.zip"
    fetch_file(CLIOPATRIA_URL, out, refresh)
    geo = RAW / "cliopatria" / "cliopatria_polities_only_v021.geojson"
    if refresh or not geo.exists():
        with zipfile.ZipFile(out) as z:
            z.extractall(out.parent)
    fetch_file(MADDISON_URL, RAW / "maddison" / "mpd2023_web.xlsx", refresh)
    for name, url in UCDP_URLS.items():
        z = RAW / "ucdp" / url.rsplit("/", 1)[1]
        fetch_file(url, z, refresh)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(z.parent)
    out = RAW / "wikidata" / "events.csv"
    if refresh or not out.exists():
        rows, header = [], None
        for qid, kind in EVENT_TYPES.items():
            for attempt in range(4):
                r = session.get(WIKIDATA_SPARQL, params={"query": WIKIDATA_EVENTS_QUERY % qid},
                                headers={"Accept": "text/csv"}, timeout=300)
                if r.status_code == 200:
                    break
                time.sleep(20 * (attempt + 1))
            r.raise_for_status()
            lines = r.content.decode("utf-8").splitlines()
            header = lines[0] + ",kind"
            rows += [line + "," + kind for line in lines[1:]]
            print(f"  Wikidata {kind}: {len(lines) - 1:,} rows")
        text = "".join(line + "\n" for line in [header] + rows)
        _write(out, text.encode("utf-8"), WIKIDATA_SPARQL)


def simplify_boundaries(src: Path, out: Path, refresh: bool) -> None:
    if out.exists() and not refresh:
        return
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError("npx (Node.js) is required to simplify map boundaries")
    subprocess.run([npx, "--yes", MAPSHAPER, str(src), "-filter-fields", "ADM0_A3,ISO_A3_EH,NAME",
                    "-simplify", "4%", "keep-shapes", "-o", "precision=0.01", "format=geojson", str(out)],
                   check=True)
    print(f"  {out.name}: {out.stat().st_size:,} bytes")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download everything")
    ap.add_argument("--skip-gdelt", action="store_true", help="skip the slow, rate-limited GDELT fetch")
    args = ap.parse_args(argv)

    cat = load_yaml("indicators.yaml")
    print("World Bank")
    fetch_wb_countries(args.refresh)
    for ind in cat["indicators"]:
        if ind["source"] in WB_SOURCE_ID:
            fetch_wb_indicator(ind["code"], args.refresh, ind["source"])
    print("UNDP HDR")
    fetch_file(HDR_URL, RAW / "undp" / "hdr25_composite_time_series.csv", args.refresh)
    print("UN World Population Prospects")
    fetch_file(WPP_URL, RAW / "un" / "wpp2024_demographic_indicators.csv.gz", args.refresh)
    print("Natural Earth")
    ne_raw = RAW / "ne" / "ne_10m_admin_0_countries_ind.geojson"
    fetch_file(NE_URL, ne_raw, args.refresh)
    simplify_boundaries(ne_raw, RAW / "ne" / "countries_ind_simplified.geojson", args.refresh)
    print("Transparency International (via Our World in Data)")
    fetch_file(CPI_URL, RAW / "ti" / "cpi.csv", args.refresh)
    print("V-Dem (via Our World in Data)")
    for ind in cat["indicators"]:
        if ind["source"] == "v-dem":
            fetch_file(f"https://ourworldindata.org/grapher/{ind['owid']}.csv?v=1&csvType=full&useColumnShortNames=true",
                       RAW / "vdem" / f"{ind['id']}.csv", args.refresh)
    print("Indian states (data.gov.in)")
    from . import india
    india.fetch(args.refresh, _get, _write)
    print("ILOSTAT and FAOSTAT")
    for ind in cat["indicators"]:
        if ind["source"] == "ilostat":
            fetch_file(f"https://rplumber.ilo.org/data/indicator/?id={ind['code']}&format=.csv", RAW / "ilostat" / f"{ind['code']}.csv", args.refresh)
    if any(i["source"] == "faostat" for i in cat["indicators"]):
        fetch_file("https://bulks-faostat.fao.org/production/Food_Security_Data_E_All_Data_(Normalized).zip",
                   RAW / "faostat" / "food_security.zip", args.refresh)
    print("Electricity (Ember)")
    fetch_file(EMBER_URL, RAW / "ember" / "yearly_generation.csv", args.refresh)
    print("Cities (GHSL Urban Centre Database)")
    for theme in ("GENERAL_CHARACTERISTICS", "GHSL"):
        fetch_file(f"{GHSL_BASE}/GHS_UCDB_THEME_{theme}_GLOBE_R2024A/V1-2/GHS_UCDB_THEME_{theme}_GLOBE_R2024A_V1_2.zip",
                   RAW / "ghsl" / f"{theme}.zip", args.refresh)
    print("Universities (OpenAlex)")
    fetch_openalex(args.refresh)
    print("OECD")
    for ind in cat["indicators"]:
        if ind["source"] == "oecd":
            fetch_oecd(ind, args.refresh)
    print("Geopolitics (UCDP events, UN votes, UNHCR)")
    fetch_geopolitics(args.refresh)
    print("History (Cliopatria, Maddison, UCDP, Wikidata)")
    fetch_history(args.refresh)
    print("Country facts (Wikidata)")
    fetch_country_facts(args.refresh)
    if not args.skip_gdelt:
        print("GDELT")
        fetch_fips_map(args.refresh)
        fetch_gdelt(args.refresh)


if __name__ == "__main__":
    main()
