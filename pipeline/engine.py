"""Deterministic ranking engine. Pure functions only: no I/O, no global state.

The browser Index Builder (site/static/js/engine.js) is a line-for-line port of
this module; tests/test_parity.py checks that both give identical results.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

HIGHER, LOWER = "higher_better", "lower_better"


@dataclass
class IndicatorSpec:
    id: str
    weight: float                 # within its pillar
    direction: str = HIGHER
    transform: str | None = None  # "log" or None
    pillar: str = "_"


@dataclass
class PillarSpec:
    id: str
    weight: float


@dataclass
class Result:
    entity_id: str
    score: float | None
    rank: int | None = None
    is_tied: bool = False
    coverage: float = 0.0
    excluded_reason: str | None = None
    pillar_scores: dict[str, float] = field(default_factory=dict)
    rank_low: int | None = None
    rank_high: int | None = None


def _transform(v: float, t: str | None) -> float | None:
    if t == "log":
        return math.log(v) if v > 0 else None
    return v


def normalise(values: dict[str, float], method: str, direction: str,
              transform: str | None) -> dict[str, float]:
    """Return 0–1 scores per entity, 1 = best. Missing entities stay missing."""
    tv = {e: _transform(v, transform) for e, v in values.items()}
    tv = {e: v for e, v in tv.items() if v is not None}
    if not tv:
        return {}
    xs = list(tv.values())
    if method == "z_score":
        mean = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs)) or 1.0
        # map z in [-3, 3] onto [0, 1] so pillars stay comparable
        out = {e: min(1.0, max(0.0, ((v - mean) / sd + 3) / 6)) for e, v in tv.items()}
    else:  # min_max
        lo, hi = min(xs), max(xs)
        span = hi - lo
        out = {e: (v - lo) / span if span else 0.5 for e, v in tv.items()}
    if direction == LOWER:
        out = {e: 1.0 - s for e, s in out.items()}
    return out


def _weighted_mean(pairs: list[tuple[float, float]], geometric: bool) -> float:
    total = sum(w for _, w in pairs)
    if geometric:
        # floor at 0.001 so a single zero doesn't zero the whole score
        return math.exp(sum(w * math.log(max(s, 0.001)) for s, w in pairs) / total)
    return sum(s * w for s, w in pairs) / total


def score(norm: dict[str, dict[str, float]], indicators: list[IndicatorSpec],
          pillars: list[PillarSpec], entities: list[str], min_coverage: float,
          aggregation: str = "arithmetic",
          weight_override: tuple[dict[str, float], dict[str, float]] | None = None) -> list[Result]:
    """Aggregate normalised indicator scores into a 0–100 score per entity.

    Coverage = share of the total (effective) weight for which the entity has data.
    Entities below min_coverage are excluded, not zero-filled. Weights are
    renormalised over the indicators an entity does have.
    """
    pw = {p.id: p.weight for p in pillars}
    iw = {i.id: i.weight for i in indicators}
    if weight_override:
        pw, iw = weight_override
    geometric = aggregation == "geometric"
    pillar_total = sum(pw.values())
    by_pillar: dict[str, list[IndicatorSpec]] = {}
    for ind in indicators:
        by_pillar.setdefault(ind.pillar, []).append(ind)
    pillar_ind_total = {p: sum(iw[i.id] for i in inds) for p, inds in by_pillar.items()}

    results = []
    for e in entities:
        pillar_scores: dict[str, float] = {}
        coverage = 0.0
        for p, inds in by_pillar.items():
            pairs = [(norm[i.id][e], iw[i.id]) for i in inds if e in norm.get(i.id, {})]
            if not pairs:
                continue
            coverage += (pw[p] / pillar_total) * sum(w for _, w in pairs) / pillar_ind_total[p]
            pillar_scores[p] = _weighted_mean(pairs, geometric)
        coverage = round(coverage, 9)
        if coverage < min_coverage:
            results.append(Result(e, None, coverage=coverage, excluded_reason="coverage_below_threshold"))
            continue
        total = _weighted_mean([(s, pw[p]) for p, s in pillar_scores.items()], geometric)
        results.append(Result(e, round(total * 100, 6), coverage=coverage,
                              pillar_scores={p: round(s * 100, 6) for p, s in pillar_scores.items()}))
    return assign_ranks(results)


def assign_ranks(results: list[Result], descending: bool = True) -> list[Result]:
    """Competition ranking (1, 2, 2, 4). Ties are scores equal at 6 decimal places."""
    ranked = [r for r in results if r.score is not None]
    ranked.sort(key=lambda r: (-r.score if descending else r.score, r.entity_id))
    prev, prev_rank = None, 0
    for i, r in enumerate(ranked, 1):
        key = round(r.score, 6)
        if key == prev:
            r.rank = prev_rank
        else:
            r.rank, prev_rank, prev = i, i, key
    counts: dict[int, int] = {}
    for r in ranked:
        counts[r.rank] = counts.get(r.rank, 0) + 1
    for r in ranked:
        r.is_tied = counts[r.rank] > 1
    unranked = sorted((r for r in results if r.score is None), key=lambda r: r.entity_id)
    return ranked + unranked


def sensitivity(norm, indicators, pillars, entities, min_coverage, aggregation,
                runs: int, spread: float, seed: int) -> dict[str, tuple[int, int]]:
    """Monte Carlo: perturb every weight by U(1-spread, 1+spread), re-rank, and
    return the 5th–95th percentile rank of each entity ranked in the base run."""
    rng = random.Random(seed)
    ranks: dict[str, list[int]] = {}
    for _ in range(runs):
        pw = {p.id: p.weight * rng.uniform(1 - spread, 1 + spread) for p in pillars}
        iw = {i.id: i.weight * rng.uniform(1 - spread, 1 + spread) for i in indicators}
        for r in score(norm, indicators, pillars, entities, min_coverage, aggregation, (pw, iw)):
            if r.rank is not None:
                ranks.setdefault(r.entity_id, []).append(r.rank)
    out = {}
    for e, rs in ranks.items():
        rs.sort()
        lo = rs[int(0.05 * (len(rs) - 1))]
        hi = rs[int(math.ceil(0.95 * (len(rs) - 1)))]
        out[e] = (lo, hi)
    return out


# ---------------------------------------------------------------- HDI (UNDP method)
HDI_GOALPOSTS = {"le": (20, 85), "eys": (0, 18), "mys": (0, 15), "gnipc": (100, 75000)}


def hdi(le: float, eys: float, mys: float, gnipc: float) -> float:
    """UNDP HDI: geometric mean of health, education and income indices."""
    def idx(v, lo, hi):
        return (min(max(v, lo), hi) - lo) / (hi - lo)
    health = idx(le, *HDI_GOALPOSTS["le"])
    education = (idx(eys, *HDI_GOALPOSTS["eys"]) + idx(mys, *HDI_GOALPOSTS["mys"])) / 2
    lo, hi = HDI_GOALPOSTS["gnipc"]
    income = (math.log(min(max(gnipc, lo), hi)) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return (health * education * income) ** (1 / 3)
