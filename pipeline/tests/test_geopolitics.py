"""Geopolitics: licences, name matching, the risk index method and the built pages."""
import json
from pathlib import Path

import pytest
import yaml

from pipeline import geopolitics

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
built = pytest.mark.skipif(not (DIST / "geopolitics" / "index.html").exists(), reason="no build in dist/")


def test_sources_are_open_and_credited():
    lic = {s["source_id"]: s for s in yaml.safe_load((ROOT / "data" / "licences.yaml").read_text(encoding="utf-8"))["sources"]}
    assert lic["ucdp"]["licence"] == "CC BY 4.0"
    assert lic["unvotes"]["licence"] == "CC0 1.0"
    assert lic["unhcr"]["licence"] == "CC BY 4.0"
    for s in ("ucdp", "unvotes", "unhcr", "gdelt"):
        assert lic[s]["tier"] == "green" and lic[s]["attribution_text"]


def test_risk_weights_sum_to_one_and_exclude_share_alike_data():
    assert sum(w for _, _, w in geopolitics.RISK_WEIGHTS) == pytest.approx(1)
    # V-Dem is CC BY-SA and must never enter a CC BY composite
    assert not any("V-Dem" in label for _, label, _ in geopolitics.RISK_WEIGHTS)


def test_ucdp_historical_names_map_to_today():
    assert geopolitics.GED_FIX["russia (soviet union)"] == "RUS"
    assert geopolitics.GED_FIX["dr congo (zaire)"] == "COD"
    assert geopolitics._norm("Côte  d'Ivoire") == "cote d'ivoire"


@built
def test_pages_relations_and_country_files():
    for p in ("", "news/", "briefing/", "conflicts/", "risk/", "un-votes/", "displacement/", "relations/"):
        assert (DIST / "geopolitics" / p / "index.html").exists(), p
    assert (DIST / "geopolitics" / "relations" / "russia-and-ukraine" / "index.html").exists()
    rus = json.loads((DIST / "geopolitics" / "data" / "RUS.json").read_text(encoding="utf-8"))
    assert "UKR" in rus["agree"] and rus["war"].get("UKR")             # votes and a recorded war with Ukraine
    hub = (DIST / "geopolitics" / "index.html").read_text(encoding="utf-8")
    assert "data-gdelt" in hub and "not checked by this site" in hub    # live news is labelled as unverified
    india = (DIST / "countries" / "india" / "index.html").read_text(encoding="utf-8")
    assert "Geopolitical risk index" in india and "UN votes in agreement with" in india


def test_bloc_memberships_are_valid_and_counts_match_official_totals():
    d = yaml.safe_load((ROOT / "data" / "blocs.yaml").read_text(encoding="utf-8"))
    counts = {b["id"]: len(b["members"]) for b in d["blocs"]}
    assert counts["nato"] == 32 and counts["eu"] == 27 and counts["oecd"] == 38 and counts["g20"] == 19
    assert counts["unsc"] == 15 and counts["au"] == 55 and counts["arab-league"] == 22
    for b in d["blocs"]:
        assert len(set(b["members"])) == len(b["members"]), b["id"]
        assert b["url"].startswith("http"), b["id"]
    assert sum(1 for x in d["blocs"] if x["id"] == "unsc" for s in x["status"].values() if s == "permanent") == 5


@built
def test_blocs_feeds_event_map_and_watchlist():
    assert (DIST / "geopolitics" / "blocs" / "nato" / "index.html").exists()
    assert (DIST / "geopolitics" / "defence" / "index.html").exists()
    assert (DIST / "geopolitics" / "watchlist" / "index.html").exists()
    ev = json.loads((DIST / "geopolitics" / "data" / "events.json").read_text(encoding="utf-8"))
    assert len(ev["points"]) > 500 and ev["from"] < ev["to"]
    import xml.etree.ElementTree as ET
    for f in ("briefing.xml", "reports.xml", "countries/india.xml"):
        root = ET.parse(DIST / "feeds" / f).getroot()
        assert root.tag == "rss" and root.find("channel/item/title") is not None, f
    india = (DIST / "countries" / "india" / "index.html").read_text(encoding="utf-8")
    assert 'data-watch="IND"' in india and "/geopolitics/blocs/brics/" in india
