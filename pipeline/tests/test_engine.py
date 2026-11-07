import math

import pytest

from pipeline import engine
from pipeline.engine import IndicatorSpec, PillarSpec


def test_min_max_scales_to_unit_interval_and_flips_direction():
    vals = {"A": 10, "B": 20, "C": 30}
    up = engine.normalise(vals, "min_max", "higher_better", None)
    down = engine.normalise(vals, "min_max", "lower_better", None)
    assert up == {"A": 0.0, "B": 0.5, "C": 1.0}
    assert down == {"A": 1.0, "B": 0.5, "C": 0.0}


def test_log_transform_drops_non_positive_values_rather_than_zero_filling():
    out = engine.normalise({"A": 0, "B": 10, "C": 100}, "min_max", "higher_better", "log")
    assert "A" not in out
    assert out["B"] == 0.0 and out["C"] == 1.0


def test_z_score_is_bounded():
    out = engine.normalise({str(i): i for i in range(100)} | {"X": 10_000}, "z_score", "higher_better", None)
    assert all(0.0 <= v <= 1.0 for v in out.values())


def _spec():
    inds = [IndicatorSpec("a", 0.5, pillar="p1"), IndicatorSpec("b", 0.5, pillar="p1"),
            IndicatorSpec("c", 1.0, pillar="p2")]
    pillars = [PillarSpec("p1", 0.5), PillarSpec("p2", 0.5)]
    return inds, pillars


def test_missing_data_is_never_scored_as_zero():
    inds, pillars = _spec()
    norm = {"a": {"X": 1.0, "Y": 1.0}, "b": {"X": 1.0}, "c": {"X": 1.0, "Y": 1.0}}
    res = {r.entity_id: r for r in engine.score(norm, inds, pillars, ["X", "Y"], 0.7)}
    # Y lacks 'b' (25% of total weight) but is re-weighted, not penalised
    assert res["Y"].coverage == pytest.approx(0.75)
    assert res["Y"].score == pytest.approx(100.0)
    assert res["X"].score == pytest.approx(100.0)


def test_entities_below_coverage_threshold_are_excluded():
    inds, pillars = _spec()
    norm = {"a": {"X": 1.0, "Y": 0.4}, "b": {"X": 1.0}, "c": {"X": 1.0}}
    res = {r.entity_id: r for r in engine.score(norm, inds, pillars, ["X", "Y"], 0.7)}
    assert res["Y"].score is None and res["Y"].rank is None
    assert res["Y"].excluded_reason == "coverage_below_threshold"
    assert res["Y"].coverage == pytest.approx(0.25)


def test_ties_share_a_rank_and_next_rank_skips():
    rs = engine.assign_ranks([engine.Result("A", 50.0), engine.Result("B", 50.0), engine.Result("C", 40.0)])
    assert [(r.entity_id, r.rank, r.is_tied) for r in rs] == [("A", 1, True), ("B", 1, True), ("C", 3, False)]


def test_geometric_mean_penalises_imbalance_more_than_arithmetic():
    inds = [IndicatorSpec("a", 0.5), IndicatorSpec("b", 0.5)]
    pillars = [PillarSpec("_", 1.0)]
    norm = {"a": {"X": 0.9, "Y": 0.5}, "b": {"X": 0.1, "Y": 0.5}}
    ar = {r.entity_id: r.score for r in engine.score(norm, inds, pillars, ["X", "Y"], 0, "arithmetic")}
    ge = {r.entity_id: r.score for r in engine.score(norm, inds, pillars, ["X", "Y"], 0, "geometric")}
    assert ar["X"] == pytest.approx(ar["Y"])
    assert ge["X"] < ge["Y"]


def test_sensitivity_is_deterministic_for_a_seed():
    inds, pillars = _spec()
    norm = {k: {e: (i * 7 + j * 3) % 10 / 10 for j, e in enumerate("ABCDEFGH")} for i, k in enumerate("abc")}
    args = (norm, inds, pillars, list("ABCDEFGH"), 0.5, "arithmetic", 200, 0.25)
    assert engine.sensitivity(*args, seed=1) == engine.sensitivity(*args, seed=1)


def test_hdi_matches_undp_published_values():
    import csv
    from pipeline.config import RAW
    path = RAW / "undp" / "hdr25_composite_time_series.csv"
    if not path.exists():
        pytest.skip("HDR 2025 file not downloaded")
    with open(path, encoding="latin-1", newline="") as f:
        rows = {r["iso3"]: r for r in csv.DictReader(f)}
    for iso in ("IND", "CHN", "NOR", "NER", "BRA"):
        r = rows[iso]
        mine = engine.hdi(*(float(r[f"{k}_2023"]) for k in ("le", "eys", "mys", "gnipc")))
        assert round(mine, 3) == pytest.approx(float(r["hdi_2023"]), abs=1e-9), iso


def test_hdi_goalposts():
    assert engine.hdi(85, 18, 15, 75000) == pytest.approx(1.0)
    assert math.isclose(engine.hdi(20, 0, 0, 100), 0.0, abs_tol=1e-12)
