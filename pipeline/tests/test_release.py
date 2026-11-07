"""Checks on the built release in dist/ (skipped until a build has run)."""
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
LATEST = ROOT / "dist" / "v1" / "latest"
pytestmark = pytest.mark.skipif(not (LATEST / "manifest.json").exists(), reason="no build in dist/")


def load(rel):
    return json.loads((LATEST / rel).read_text(encoding="utf-8"))


def test_every_published_source_is_green_and_licence_checked():
    lic = {s["source_id"]: s for s in yaml.safe_load((ROOT / "data" / "licences.yaml").read_text(encoding="utf-8"))["sources"]}
    for ind in load("indicators.json"):
        src = lic[ind["source"]]
        assert src["tier"] == "green", ind["indicator_id"]
        assert src["licence_checked_on"], src["source_id"]


def test_matrix_excludes_display_only_and_no_modification_sources():
    m = load("matrix.json")
    ids = {i["indicator_id"] for i in m["indicators"]}
    assert "cpi" not in ids
    assert len(m["values"]) == len(m["entities"]) and all(len(r) == len(ids) for r in m["values"])


def test_observed_values_carry_provenance():
    india = load("entities/country/IND.json")
    for ind_id, v in india["latest"].items():
        for k in ("value", "year", "status", "source", "source_licence", "source_url", "retrieved_at"):
            assert v.get(k) not in (None, ""), (ind_id, k)


def test_no_zero_filled_ranking_scores():
    for r in load("rankings.json"):
        res = load(f"rankings/{r['ranking_id']}/{r['current_version']}.json")["results"]
        for row in res:
            if row["score"] is None:
                assert row["rank"] is None and row["excluded_reason"]
            else:
                assert row["rank"] is not None


def test_manifest_checksums_match_files():
    import hashlib
    m = load("manifest.json")
    for f in m["files"][:50]:
        assert hashlib.sha256((LATEST / f["path"]).read_bytes()).hexdigest() == f["sha256"], f["path"]


def test_fits_cloudflare_static_asset_limits():
    dist = ROOT / "dist"
    files = [p for p in dist.rglob("*") if p.is_file()]
    assert len(files) < 20_000                                  # Workers Free: 20,000 files per version
    too_big = [str(p.relative_to(dist)) for p in files if p.stat().st_size > 25 * 1024 * 1024]
    assert not too_big, too_big                                  # 25 MiB per file
