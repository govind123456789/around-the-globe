"""Reports: config, generated wording rules and the built pages and builder data."""
import json
from pathlib import Path

import pytest
import yaml

from pipeline import reports

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
built = pytest.mark.skipif(not (DIST / "reports" / "index.html").exists(), reason="no build in dist/")
KINDS = {"world_trend", "leaders", "movers", "shares", "regions", "gap"}


def test_report_sections_use_known_kinds_and_indicators():
    inds = {i["id"] for i in yaml.safe_load((ROOT / "data" / "indicators.yaml").read_text(encoding="utf-8"))["indicators"]}
    cfg = yaml.safe_load((ROOT / "data" / "reports.yaml").read_text(encoding="utf-8"))["reports"]
    assert len({r["id"] for r in cfg}) == len(cfg)
    for r in cfg:
        for s in r["sections"]:
            assert s["kind"] in KINDS and s["indicator"] in inds, (r["id"], s)


def test_wording_helpers():
    assert reports.lc("GDP per capita") == "GDP per capita"
    assert reports.lc("Life expectancy") == "life expectancy"
    assert reports.additive({"unit": "current US$", "name": "Manufacturing output"})
    assert not reports.additive({"unit": "current US$", "name": "GNI per capita (Atlas method)"})
    assert not reports.additive({"unit": "% of GDP", "name": "Trade"})


@built
def test_reports_render_with_findings_and_no_unfilled_values():
    cfg = yaml.safe_load((ROOT / "data" / "reports.yaml").read_text(encoding="utf-8"))["reports"]
    for r in cfg:
        html = (DIST / "reports" / r["id"] / "index.html").read_text(encoding="utf-8")
        assert 'class="rp-finding"' in html, r["id"]
        assert "None" not in html.split("<main", 1)[1], r["id"]


@built
def test_builder_data_ranks_totals_by_size_and_covers_every_country():
    meta = json.loads((DIST / "reports" / "data" / "meta.json").read_text(encoding="utf-8"))
    assert meta["inds"]["power-emissions"]["dir"] == "neutral"         # a total: size, not good or bad
    assert meta["inds"]["coal-power-share"]["dir"] == "lower_better"
    chn = json.loads((DIST / "reports" / "data" / "CHN.json").read_text(encoding="utf-8"))
    assert chn["ind"]["manufacturing-output"][2] == 1                   # largest manufacturer ranks first
    assert len(list((DIST / "reports" / "data").glob("*.json"))) >= 200
