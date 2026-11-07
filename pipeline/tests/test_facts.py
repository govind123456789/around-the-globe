"""Country facts: cleaning rules, overrides and what the built release contains."""
import csv
import json
from pathlib import Path

import pytest
import yaml

from pipeline import facts

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "dist" / "v1" / "latest"
built = pytest.mark.skipif(not (LATEST / "manifest.json").exists(), reason="no build in dist/")

ENTITIES = {
    "AAA": {"type": "country", "name": "Aland", "slug": "aland"},
    "BBB": {"type": "country", "name": "Bland", "slug": "bland"},
    "CCC": {"type": "country", "name": "Cland", "slug": "cland"},
    "WLD": {"type": "country_group", "name": "World", "slug": "world"},
}


def write(folder, name, rows):
    with open(folder / f"{name}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["iso3", "c", "v", "vLabel", "extra"])
        w.writeheader()
        for iso, label, extra in rows:
            w.writerow({"iso3": iso, "c": "http://x/Q1", "v": "http://x/Q2", "vLabel": label, "extra": extra})


def test_highest_elevation_wins_and_ties_are_stable():
    assert facts.clean_highest({("Peak", "2706.0"), ("Peak", "4466.0")}) == {"name": "Peak", "elevation_m": 4466}
    assert facts.clean_highest({("B", "100"), ("A", "100")})["name"] == "A"
    assert facts.clean_highest({("Peak", "")}) == {"name": "Peak", "elevation_m": None}


def test_currency_is_unique_by_code():
    out = facts.clean_currency({("zloty", "PLN"), ("Zloty", "PLN"), ("Local", "")})
    assert sorted(c["code"] or "-" for c in out) == ["-", "PLN"]


def test_borders_are_symmetric_and_exclude_unknown_codes():
    out = facts.symmetric_borders({"AAA": {("Bland", "BBB"), ("Elsewhere", "ZZZ"), ("Aland", "AAA")}}, {"AAA", "BBB"})
    assert out == {"AAA": {"BBB"}, "BBB": {"AAA"}}


def test_load_filters_qids_and_non_latin_domains_and_applies_overrides(tmp_path):
    write(tmp_path, "highest_point", [("AAA", "Q130018", "6190"), ("BBB", "Hill", "10.4")])
    write(tmp_path, "internet_domain", [("AAA", ".aa", ""), ("AAA", ".भारत", "")])
    write(tmp_path, "languages", [("AAA", "One", ""), ("CCC", "Wrong", "")])
    write(tmp_path, "neighbours", [("AAA", "Bland", "BBB")])
    out = facts.load(ENTITIES, tmp_path, overrides={"CCC": {"languages": ["Right"]}})
    assert "highest_point" not in out["AAA"]                 # raw Q-id labels are dropped
    assert out["BBB"]["highest_point"] == {"name": "Hill", "elevation_m": 10}
    assert out["AAA"]["internet_domain"] == [".aa"]
    assert out["CCC"]["languages"] == ["Right"]
    assert [b["entity_id"] for b in out["BBB"]["borders"]] == ["AAA"]
    assert "WLD" not in out


def test_every_override_is_for_a_known_field():
    allowed = {"languages", "currency", "calling_code", "internet_domain", "drives_on", "highest_point"}
    data = yaml.safe_load((ROOT / "data" / "country_facts_overrides.yaml").read_text(encoding="utf-8"))
    for iso, fields in data["overrides"].items():
        assert set(fields) <= allowed, iso


def country(iso):
    return json.loads((LATEST / "entities" / "country" / f"{iso}.json").read_text(encoding="utf-8"))


@built
def test_release_has_the_corrected_facts():
    usa, tur, arg, fra = country("USA")["facts"], country("TUR")["facts"], country("ARG")["facts"], country("FRA")["facts"]
    assert usa["languages"] == ["English"] and usa["highest_point"]["name"] == "Denali"
    assert tur["calling_code"] == ["+90"]
    assert arg["drives_on"] == "right"
    assert [c["code"] for c in fra["currency"]] == ["EUR"]
    india = country("IND")["facts"]
    assert india["internet_domain"] == [".in"]
    assert {"PAK", "CHN"} <= {b["entity_id"] for b in india["borders"]}


@built
def test_release_borders_are_symmetric_and_palestine_is_merged():
    pse = country("PSE")["facts"]
    assert "ISR" in {b["entity_id"] for b in pse["borders"]}
    assert "PSE" in {b["entity_id"] for b in country("ISR")["facts"]["borders"]}
    assert len(pse["calling_code"]) == 1


@built
def test_countries_without_facts_have_an_empty_record():
    assert country("XKX")["facts"] == {}


@built
def test_no_raw_qids_anywhere_in_facts():
    index = json.loads((LATEST / "entities" / "country.json").read_text(encoding="utf-8"))
    for c in index:
        text = json.dumps(country(c["entity_id"])["facts"], ensure_ascii=False)
        assert not facts.re.search(r'"Q\d+"', text), c["entity_id"]
