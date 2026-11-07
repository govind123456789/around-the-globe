"""The browser engine (site/static/js/engine.js) must rank exactly like pipeline/engine.py."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import engine
from pipeline.engine import IndicatorSpec, PillarSpec

JS = Path(__file__).resolve().parents[2] / "site" / "static" / "js" / "engine.js"
node = shutil.which("node")


def fixture(seed=7, n=60):
    rng = random.Random(seed)
    ents = [f"E{i:02d}" for i in range(n)]
    inds = [("a", "higher_better", None, "p1", 0.6), ("b", "lower_better", None, "p1", 0.4),
            ("c", "higher_better", "log", "p2", 1.0), ("d", "higher_better", None, "p3", 0.5),
            ("e", "lower_better", None, "p3", 0.5)]
    values = {i[0]: {e: round(rng.uniform(1, 1000), 3) for e in ents if rng.random() > 0.15} for i in inds}
    pillars = [("p1", 0.35), ("p2", 0.35), ("p3", 0.30)]
    return ents, inds, values, pillars


def python_ranks(ents, inds, values, pillars, method, agg):
    specs = [IndicatorSpec(i, w, d, t, p) for i, d, t, p, w in inds]
    norm = {s.id: engine.normalise(values[s.id], method, s.direction, s.transform) for s in specs}
    res = engine.score(norm, specs, [PillarSpec(p, w) for p, w in pillars], ents, 0.7, agg)
    return [(r.entity_id, r.rank, None if r.score is None else round(r.score, 6)) for r in res]


def js_ranks(ents, inds, values, pillars, method, agg):
    prog = f"""
const E = require({json.dumps(str(JS))});
const ents = {json.dumps(ents)}, inds = {json.dumps(inds)}, values = {json.dumps(values)}, pillars = {json.dumps(pillars)};
const norm = {{}}, specs = [];
for (const [id, dir, t, p, w] of inds) {{ norm[id] = E.normalise(values[id], "{method}", dir, t); specs.push({{id, weight: w, pillar: p}}); }}
const res = E.score(norm, specs, pillars.map(([id, weight]) => ({{id, weight}})), ents, 0.7, "{agg}");
console.log(JSON.stringify(res.map(r => [r.entity_id, r.rank, r.score === null ? null : Math.round(r.score * 1e6) / 1e6])));
"""
    out = subprocess.run([node, "-e", prog], capture_output=True, text=True, check=True).stdout
    return [tuple(x) for x in json.loads(out)]


@pytest.mark.skipif(not node, reason="Node.js not installed")
@pytest.mark.parametrize("method,agg", [("min_max", "arithmetic"), ("min_max", "geometric"), ("z_score", "arithmetic")])
def test_js_and_python_engines_agree(method, agg):
    ents, inds, values, pillars = fixture()
    py = python_ranks(ents, inds, values, pillars, method, agg)
    js = js_ranks(ents, inds, values, pillars, method, agg)
    assert [(e, r) for e, r, _ in js] == [(e, r) for e, r, _ in py]
    for (_, _, a), (_, _, b) in zip(js, py):
        assert (a is None and b is None) or abs(a - b) < 1e-5
