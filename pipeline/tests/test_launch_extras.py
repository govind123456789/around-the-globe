"""UN projections, Index Builder stability, embeds, share cards and self-hosted assets."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
LATEST = DIST / "v1" / "latest"
ENGINE = ROOT / "site" / "static" / "js" / "engine.js"
node = shutil.which("node")
built = pytest.mark.skipif(not (LATEST / "manifest.json").exists(), reason="no build in dist/")


@pytest.mark.skipif(not node, reason="Node.js not installed")
def test_builder_stability_is_deterministic_and_brackets_the_rank():
    prog = f"""
const E = require({json.dumps(str(ENGINE))});
const ents = Array.from({{length: 40}}, (_, i) => "E" + i);
const mk = k => Object.fromEntries(ents.map((e, i) => [e, ((i * k * 7) % 40) / 39]));
const norm = {{a: mk(1), b: mk(3), c: mk(5)}};
const specs = [{{id: "a", weight: 50, pillar: "p"}}, {{id: "b", weight: 30, pillar: "p"}}, {{id: "c", weight: 20, pillar: "q"}}];
const pillars = [{{id: "p", weight: 60}}, {{id: "q", weight: 40}}];
const base = E.score(norm, specs, pillars, ents, 0.7, "arithmetic");
const run = () => E.sensitivity(norm, specs, pillars, ents, 0.7, "arithmetic", 200, 0.25, 7);
const x = run(), y = run();
console.log(JSON.stringify({{same: JSON.stringify(x) === JSON.stringify(y), n: Object.keys(x).length,
  ok: base.every(r => x[r.entity_id][0] <= x[r.entity_id][1])}}));
"""
    out = json.loads(subprocess.run([node, "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert out == {"same": True, "n": 40, "ok": True}


@built
def test_un_projection_reaches_2100_and_median_age_is_published():
    india = json.loads((LATEST / "entities" / "country" / "IND.json").read_text(encoding="utf-8"))
    series = dict(map(tuple, india["population_projection"]["series"]))
    assert series[2100] > 1e9 and series[1950] < series[2050]
    assert 15 < india["latest"]["median-age"]["value"] < 50
    assert india["latest"]["median-age"]["source_licence"] == "CC BY 3.0 IGO"


@built
def test_pages_load_nothing_from_third_parties():
    hosts = re.compile(r"(fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|unpkg\.com|cdnjs)")
    for page in ("index.html", "countries/india/index.html", "rankings/population/index.html", "countries/india/history/index.html"):
        assert not hosts.search((DIST / page).read_text(encoding="utf-8")), page
    for js in (DIST / "static" / "js").glob("*.js"):
        assert not hosts.search(js.read_text(encoding="utf-8")), js.name
    assert (DIST / "static" / "vendor" / "maplibre-gl.js").exists()
    fonts = (DIST / "static" / "css" / "fonts.css").read_text(encoding="utf-8")
    for url in re.findall(r"url\((/static/fonts/[^)]+)\)", fonts):
        assert (DIST / url.lstrip("/")).exists(), url


@built
def test_embeds_exist_are_noindex_and_credit_the_source():
    html = (DIST / "embed" / "rankings" / "population" / "index.html").read_text(encoding="utf-8")
    assert 'content="noindex"' in html and "Source:" in html and "licence" not in html.lower().split("<body")[0]
    assert "embed/" not in (DIST / "sitemap.xml").read_text(encoding="utf-8")


@built
def test_share_cards_are_the_right_size_and_linked():
    for rel in ("default.png", "world.png", "countries/india.png", "rankings/population.png"):
        with Image.open(DIST / "og" / rel) as img:
            assert img.size == (1200, 630), rel
    assert 'og/countries/india.png"' in (DIST / "countries" / "india" / "index.html").read_text(encoding="utf-8")


@built
def test_history_labels_are_renamed():
    mali = json.loads((DIST / "history" / "country" / "MLI.json").read_text(encoding="utf-8"))
    assert "Mali Federation" not in [p["name"] for p in mali["polities"]]


def test_chart_axis_reaches_the_highest_value():
    from pipeline import svg
    for lo, hi in ((0, 1.68e9), (0, 7.3), (10, 99), (-3, 4.1), (0, 100)):
        assert svg._nice_ticks(lo, hi)[-1] >= hi, (lo, hi)
    assert svg.compact(0) == "0"
