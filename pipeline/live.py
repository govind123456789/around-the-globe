"""Live world estimates: simple extrapolations from the latest published world figures.

These are estimates, not measurements. Population grows from its latest mid-year figure at
the birth rate minus the death rate. Year-to-date counts apply annual rates to the estimated
population. site/static/js/live.js is a port of estimate(); tests check that the two agree.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone


def baseline(model) -> dict | None:
    """Inputs for the counters, from the World row of each indicator."""
    get = lambda ind: model.latest("WLD", ind)
    pop, births, deaths, co2 = get("population"), get("birth-rate"), get("death-rate"), get("co2-per-capita")
    if not (pop and births and deaths):
        return None
    return {"population": pop[1], "population_year": pop[0], "birth_rate": births[1], "birth_year": births[0],
            "death_rate": deaths[1], "death_year": deaths[0], "co2_pc": co2[1] if co2 else None,
            "co2_year": co2[0] if co2 else None}


def _utc_ms(y: int, m: int = 1, d: int = 1) -> float:
    return datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000


def estimate(b: dict, now_ms: float) -> dict:
    """Same arithmetic as estimate() in site/static/js/live.js."""
    year_ms = 365.2425 * 24 * 3600 * 1000
    t0 = _utc_ms(int(b["population_year"]), 7, 1)                 # the population figure is mid-year
    rate = (b["birth_rate"] - b["death_rate"]) / 1000
    pop = b["population"] * math.exp(rate * (now_ms - t0) / year_ms)
    year = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).year
    start, end = _utc_ms(year), _utc_ms(year + 1)
    frac = (now_ms - start) / (end - start)
    births = b["birth_rate"] / 1000 * pop * frac
    deaths = b["death_rate"] / 1000 * pop * frac
    co2 = b["co2_pc"] * pop * frac if b.get("co2_pc") is not None else None
    return {"population": pop, "births": births, "deaths": deaths, "growth": births - deaths, "co2": co2}
