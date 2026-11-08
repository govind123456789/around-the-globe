"""The Lab: statistics, browser/Python parity, findings and pages."""
import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import lab

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "dist"
JS = ROOT / "site" / "static" / "js" / "lab.js"
node = shutil.which("node")
built = pytest.mark.skipif(not (DIST / "lab" / "correlations.json").exists(), reason="no build in dist/")

X = [3.1, 1.2, 5.5, 5.5, 9.0, 2.2, 7.7, 4.4]
Y = [2.0, 1.0, 4.0, 6.0, 8.5, 2.5, 7.0, 3.0]


def test_ranks_share_ties():
    assert lab.ranks([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]


def test_spearman_is_one_for_any_increasing_relationship():
    xs = [1, 2, 3, 4, 5, 6]
    assert lab.spearman(xs, [math.exp(x) for x in xs]) == pytest.approx(1)
    assert lab.spearman(xs, [-x ** 3 for x in xs]) == pytest.approx(-1)


def test_partial_correlation_removes_a_shared_cause():
    # x and y only correlate through z: r_xy = r_xz * r_yz, so the partial is zero
    assert lab.partial(0.48, 0.8, 0.6) == pytest.approx(0, abs=1e-12)


def test_ols_recovers_a_line():
    a, b, r2 = lab.ols([0, 1, 2, 3], [1, 3, 5, 7])
    assert (a, b, r2) == (pytest.approx(1), pytest.approx(2), pytest.approx(1))


@pytest.mark.skipif(not node, reason="Node.js not installed")
def test_browser_statistics_match_python():
    prog = f"const S=require({json.dumps(str(JS))});const x={json.dumps(X)},y={json.dumps(Y)};" \
           "console.log(JSON.stringify({r:S.pearson(x,y),rho:S.spearman(x,y),ranks:S.ranks(x),fit:S.ols(x,y)}))"
    js = json.loads(subprocess.run([node, "-e", prog], capture_output=True, text=True, check=True).stdout)
    assert js["r"] == pytest.approx(lab.pearson(X, Y), rel=1e-12)
    assert js["rho"] == pytest.approx(lab.spearman(X, Y), rel=1e-12)
    assert js["ranks"] == lab.ranks(X)
    a, b, _ = lab.ols(X, Y)
    assert (js["fit"]["a"], js["fit"]["b"]) == (pytest.approx(a), pytest.approx(b))


def test_leaf_order_keeps_close_items_together():
    d = [[0, .1, .9, .9], [.1, 0, .9, .9], [.9, .9, 0, .2], [.9, .9, .2, 0]]
    order = lab.leaf_order(list("abcd"), d)
    assert sorted(order) == [0, 1, 2, 3]
    assert abs(order.index(0) - order.index(1)) == 1 and abs(order.index(2) - order.index(3)) == 1


@built
def test_correlation_matrix_is_square_symmetric_and_bounded():
    c = json.loads((DIST / "lab" / "correlations.json").read_text(encoding="utf-8"))
    n = len(c["ids"])
    assert n > 100 and len(c["rho"]) == n and "cpi" not in c["ids"] and "news-share" not in c["ids"]
    for i in range(n):
        assert c["rho"][i][i] == 1
        for j in range(n):
            v = c["rho"][i][j]
            assert v == c["rho"][j][i]
            assert v is None or -1 <= v <= 1
            assert i == j or v is None or c["n"][i][j] >= lab.MIN_N


@built
def test_findings_are_complete_and_links_are_not_definitional():
    f = json.loads((DIST / "lab" / "findings.json").read_text(encoding="utf-8"))
    assert f["performers"] and f["movers"] and f["links"]
    for p in f["performers"]:
        assert len(p["above"]) == 4 and len(p["below"]) == 4 and p["n"] >= lab.MIN_N
    for k in f["links"]:
        assert k["n"] >= 80 and abs(k["partial"]) >= .35 and k["a_dim"] != k["b_dim"]
        for side in (k["a"], k["b"]):
            assert not set(lab.FAMILY_LISTS["hdr"] + lab.FAMILY_LISTS["income"] + lab.FAMILY_LISTS["size"]) & {side}


@built
def test_lab_pages_exist_and_are_in_nav_and_sitemap():
    for page in ("lab", "lab/scatter", "lab/correlations", "lab/findings", "lab/data"):
        html = (DIST / page / "index.html").read_text(encoding="utf-8")
        assert 'href="/lab/"' in html
    assert "/lab/findings/" in (DIST / "sitemap.xml").read_text(encoding="utf-8")
    data = (DIST / "lab" / "data" / "index.html").read_text(encoding="utf-8")
    assert "observations.parquet" in data and "indicator_id" in data
