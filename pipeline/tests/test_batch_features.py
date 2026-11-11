"""Crisis tracker, power index, sanctions, alerts, Lab tools, regional reports, embeds, translations
and the ILOSTAT/FAOSTAT indicators."""
import json
from pathlib import Path

import pytest
import yaml

from pipeline import geopolitics, standout

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
built = pytest.mark.skipif(not (DIST / "geopolitics" / "crises" / "index.html").exists(), reason="no build in dist/")


def test_power_weights_sum_to_one_and_crises_are_well_formed():
    assert sum(w for _, _, w in geopolitics.POWER_WEIGHTS) == pytest.approx(1)
    crises = yaml.safe_load((ROOT / "data" / "blocs.yaml").read_text(encoding="utf-8"))["crises"]
    assert len({c["id"] for c in crises}) == len(crises)
    for c in crises:
        assert c["countries"] and c["since"] >= 2000 and c["news"], c["id"]


def test_month_bars_and_trend_slope():
    svg = geopolitics.month_bars([("2025-01", 10), ("2025-02", 30)])
    assert svg.count("<rect") == 2 and "2025" in svg
    assert standout._ols_slope([(2000, 1), (2001, 3), (2002, 5)]) == pytest.approx(2)


def test_new_sources_are_open():
    lic = {s["source_id"]: s for s in yaml.safe_load((ROOT / "data" / "licences.yaml").read_text(encoding="utf-8"))["sources"]}
    for s in ("ofac", "ilostat", "faostat"):
        assert lic[s]["tier"] == "green" and lic[s]["commercial_ok"], s


@built
def test_crisis_power_sanctions_and_embed_pages():
    for p in ("crises/russia-ukraine", "crises/sudan", "power", "sanctions"):
        assert (DIST / "geopolitics" / p / "index.html").exists(), p
    power = (DIST / "geopolitics" / "power" / "index.html").read_text(encoding="utf-8")
    assert "United States" in power and "China" in power
    assert (DIST / "embed" / "risk" / "ukraine" / "index.html").exists()
    assert (DIST / "embed" / "crisis" / "sudan" / "index.html").exists()
    assert "<rss" in (DIST / "feeds" / "alerts.xml").read_text(encoding="utf-8")


@built
def test_lab_tools_timeline_regions_and_translation():
    for p in ("lab/twins", "lab/targets", "lab/coverage", "lab/fit", "explore/timeline", "reports/regions/south-asia"):
        assert (DIST / p / "index.html").exists(), p
    fit = json.loads((DIST / "lab" / "fit" / "data.json").read_text(encoding="utf-8"))
    assert len(fit["countries"]) > 100 and any(f["key"] == "peace" for f in fit["factors"])
    risk = json.loads((DIST / "explore" / "timeline" / "data" / "risk.json").read_text(encoding="utf-8"))
    assert len(risk["breaks"]) == 6 and "UKR" in risk["data"]
    assert "/static/js/i18n.js" in (DIST / "index.html").read_text(encoding="utf-8")
    india = (DIST / "countries" / "india" / "index.html").read_text(encoding="utf-8")
    assert "Time twins" in india and "Years to target" in india


@built
def test_ilostat_and_faostat_indicators_have_data():
    for ind in ("youth-neet", "informal-employment", "severe-food-insecurity", "adult-obesity"):
        d = json.loads((DIST / "v1" / "latest" / "indicators" / f"{ind}.json").read_text(encoding="utf-8"))
        assert len(d["data"]) > 60, ind


@built
def test_quiz_city_pages_home_and_grouped_nav():
    quiz = json.loads((DIST / "quiz" / "data.json").read_text(encoding="utf-8"))
    assert len(quiz["inds"]) >= 15 and len(quiz["c"]) > 80
    cities = list((DIST / "cities").glob("*/index.html"))
    assert len(cities) > 500
    tokyo = next(p for p in cities if p.parent.name.startswith("tokyo"))
    assert "Population since 1975" in tokyo.read_text(encoding="utf-8")
    home = (DIST / "index.html").read_text(encoding="utf-8")
    assert "This week" in home and "/geopolitics/crises/" in home
    power = (DIST / "geopolitics" / "power" / "index.html").read_text(encoding="utf-8")
    assert 'class="geo-groups"' in power and "Power &amp; alignment" in power
