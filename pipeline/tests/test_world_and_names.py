"""World totals, live estimates, plain names, question tabs and wide ranking tables."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from pipeline import build_data, live

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "site" / "static" / "js" / "live.js"
LATEST = ROOT / "dist" / "v1" / "latest"
node = shutil.which("node")
built = pytest.mark.skipif(not (LATEST / "manifest.json").exists(), reason="no build in dist/")


def data(name):
    return yaml.safe_load((ROOT / "data" / name).read_text(encoding="utf-8"))


BASE = {"population": 8.2e9, "population_year": 2025, "birth_rate": 16.5, "birth_year": 2024,
        "death_rate": 7.6, "death_year": 2024, "co2_pc": 4.7, "co2_year": 2024}
MID_2025 = 1751328000000      # 2025-07-01T00:00:00Z
MAR_2026 = 1772323200000      # 2026-03-01T00:00:00Z


def test_population_estimate_equals_published_figure_at_mid_year():
    assert live.estimate(BASE, MID_2025)["population"] == pytest.approx(8.2e9)


def test_estimates_grow_and_net_growth_is_births_minus_deaths():
    v = live.estimate(BASE, MAR_2026)
    assert v["population"] > 8.2e9
    assert v["growth"] == pytest.approx(v["births"] - v["deaths"])
    assert 0 < v["deaths"] < v["births"]


@pytest.mark.skipif(not node, reason="Node.js not installed")
def test_browser_and_python_estimates_agree():
    prog = f"const L=require({json.dumps(str(JS))});console.log(JSON.stringify(L.estimate({json.dumps(BASE)},{MAR_2026})))"
    js = json.loads(subprocess.run([node, "-e", prog], capture_output=True, text=True, check=True).stdout)
    py = live.estimate(BASE, MAR_2026)
    for k, v in py.items():
        assert js[k] == pytest.approx(v, rel=1e-9), k


def test_rankings_use_the_shared_date_window():
    r = data("rankings.yaml")
    assert r["single_defaults"]["reference_year"] == build_data.REF_YEAR
    assert r["single_defaults"]["max_data_age"] == build_data.REF_AGE
    for c in r["composites"]:      # the Index Builder must match the composites it starts from
        assert (c["reference_year"], c["max_data_age"]) == (build_data.REF_YEAR, build_data.REF_AGE), c["id"]


def test_question_indicators_exist_and_have_a_direction():
    inds = {i["id"]: i for i in data("indicators.yaml")["indicators"]}
    for q in data("country_questions.yaml")["questions"]:
        for ind in q["indicators"]:
            assert inds[ind]["direction"] != "neutral", (q["id"], ind)


def test_wide_ranking_columns_exist():
    inds = {i["id"] for i in data("indicators.yaml")["indicators"]}
    for s in data("rankings.yaml")["single"]:
        for col in s.get("columns", []):
            assert col["id"] == "world_share" or col["id"] in inds, (s["id"], col["id"])


@built
def test_country_names_are_plain_and_have_flags():
    countries = json.loads((LATEST / "entities" / "country.json").read_text(encoding="utf-8"))
    names = {c["entity_id"]: c["name"] for c in countries}
    assert not [n for n in names.values() if "," in n or "Rep." in n or " SAR" in n]
    assert names["KOR"] == "South Korea" and names["EGY"] == "Egypt"
    assert len({c["slug"] for c in countries}) == len(countries)
    missing = []
    for c in countries:
        iso2 = json.loads((LATEST / "entities" / "country" / f"{c['entity_id']}.json").read_text(encoding="utf-8"))["attributes"]["iso2"]
        if not (ROOT / "site" / "static" / "flags" / f"{iso2.lower()}.svg").exists():
            missing.append(c["entity_id"])
    assert missing == ["CHI"]       # the Channel Islands have no single flag


@built
def test_rankings_show_the_same_latest_year_as_country_pages():
    res = json.loads((LATEST / "rankings" / "population" / "1.0.0.json").read_text(encoding="utf-8"))["results"]
    row = next(r for r in res if r["entity_id"] == "IND")
    india = json.loads((LATEST / "entities" / "country" / "IND.json").read_text(encoding="utf-8"))
    assert row["year"] == india["latest"]["population"]["year"]
    assert row["score"] == india["latest"]["population"]["value"]


@built
def test_world_file_has_totals_above_country_values():
    world = json.loads((LATEST / "entities" / "world.json").read_text(encoding="utf-8"))["indicators"]
    india = json.loads((LATEST / "entities" / "country" / "IND.json").read_text(encoding="utf-8"))
    assert world["population"]["latest"]["value"] > 5 * india["latest"]["population"]["value"]
    assert world["gdp"]["latest"]["value"] > 1e13


@built
def test_news_coverage_stays_out_of_the_index_builder():
    m = json.loads((LATEST / "matrix.json").read_text(encoding="utf-8"))
    assert not {"news-share", "news-tone"} & {i["indicator_id"] for i in m["indicators"]}
    assert len(m["iso2"]) == len(m["entities"])
