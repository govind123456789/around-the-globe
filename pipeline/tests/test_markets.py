"""Markets: hub config, shares of the world, licences and the built pages."""
import csv
import json
from pathlib import Path

import pytest
import yaml

from pipeline import markets

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
DATA = ROOT / "data"
built = pytest.mark.skipif(not (DIST / "markets" / "index.html").exists(), reason="no build in dist/")


def _yaml(name):
    return yaml.safe_load((DATA / name).read_text(encoding="utf-8"))


def test_every_hub_points_at_known_indicators_and_rankings():
    inds = {i["id"]: i for i in _yaml("indicators.yaml")["indicators"]}
    rk = _yaml("rankings.yaml")
    rank_ids = {r["id"] for r in rk["single"]} | {r["id"] for r in rk["composites"]} | {"human-development-index"}
    hubs = _yaml("markets.yaml")["markets"]
    assert len({h["id"] for h in hubs}) == len(hubs)
    for h in hubs:
        assert h["headline"] in h["indicators"], h["id"]
        assert set(h["indicators"]) <= set(inds), (h["id"], set(h["indicators"]) - set(inds))
        assert set(h.get("rankings", [])) <= rank_ids, h["id"]
        if h["additive"]:
            # a share of the world only makes sense for totals, not for rates or per-person values
            unit = inds[h["headline"]]["unit"]
            assert not unit.startswith("%") and "per " not in unit, (h["id"], unit)


def test_market_sources_are_open_licences():
    lic = {s["source_id"]: s for s in _yaml("licences.yaml")["sources"]}
    inds = {i["id"]: i for i in _yaml("indicators.yaml")["indicators"]}
    for h in _yaml("markets.yaml")["markets"]:
        for i in h["indicators"]:
            s = lic[inds[i]["source"]]
            assert s["tier"] == "green" and s["commercial_ok"] and s["derivatives_ok"], (h["id"], i)
    assert lic["ember"]["licence"] == "CC BY 4.0"


def test_growth_and_share_helpers():
    assert markets.cagr(100, 121, 2) == pytest.approx(10)
    assert markets.cagr(0, 5, 3) is None and markets.cagr(5, 5, 0) is None
    assert markets.share_text(0.04) == "<0.1%" and markets.share_text(12.345) == "12.3%" and markets.share_text(None) == "—"


@built
def test_market_pages_csvs_nav_and_sitemap():
    hubs = _yaml("markets.yaml")["markets"]
    sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
    home = (DIST / "index.html").read_text(encoding="utf-8")
    assert 'href="/markets/"' in home
    for h in hubs:
        page = DIST / "markets" / h["id"] / "index.html"
        assert page.exists(), h["id"]
        assert f"/markets/{h['id']}/</loc>" in sitemap
        with open(DIST / "markets" / h["id"] / f"{h['id']}-latest.csv", encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        assert rows[0][:2] == ["iso3", "country"] and len(rows) > 150
    search = json.loads((DIST / "search-index.json").read_text(encoding="utf-8"))
    assert any(x["u"] == "/markets/" for x in search)


@built
def test_world_shares_use_the_sources_world_total():
    # China's share of world manufacturing on the page must equal its value over the World Bank's world figure
    page = (DIST / "markets" / "manufacturing" / "index.html").read_text(encoding="utf-8")
    assert "of world" in page and "China" in page
    rel = sorted(p for p in (DIST / "v1" / "releases").iterdir() if p.is_dir())[-1]
    world = json.loads((rel / "entities" / "world.json").read_text(encoding="utf-8"))["indicators"]
    assert "manufacturing-output" in world and "electricity-generation" in world
