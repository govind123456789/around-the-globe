"""Trust levels for every value, from data/trust.yaml (the methodology page is generated from the same file).

Each value gets penalty points for its age beyond the source's usual publication lag, for the kind of source,
and for being flagged as an estimate or a projection. 0 points is High, 1-2 Medium, 3+ Low; a value more than
`old_after` years past the lag is Low regardless. Every level comes with the reasons that produced it.
"""
from __future__ import annotations

from .config import load_yaml

_CFG: dict | None = None


def cfg() -> dict:
    global _CFG
    if _CFG is None:
        _CFG = load_yaml("trust.yaml")
    return _CFG


def level(source: str, year: int | None, release_year: int, status: str | None = "measured", c: dict | None = None) -> dict:
    """{"level": high|medium|low, "label", "icon", "points", "reasons": [...]}"""
    c = c or cfg()
    src = c["sources"].get(source) or c["sources"]["site"]
    stype = c["source_types"][src["type"]]
    lag = src.get("lag", c["freshness"]["default_lag"])
    reasons, points, forced_low = [], 0, False
    if year is None:
        return {"level": "low", **_lv(c, "low"), "points": None, "reasons": ["No data year"]}
    age = release_year - year
    over = age - lag
    if over > c["freshness"]["old_after"]:
        forced_low = True
        reasons.append(f"Data from {year}: {age} years old, well past this source's usual {lag}-year lag")
    elif over > c["freshness"]["aging_after"]:
        points += 1
        reasons.append(f"Data from {year}: {age} years old, older than this source usually is")
    else:
        reasons.append(f"Data from {year}: recent for this source")
    if stype["points"]:
        points += stype["points"]
    reasons.append(stype["label"])
    sp = c["status"].get(status or "measured", 0)
    if sp:
        points += sp
        reasons.append("The source marks this value as " + ("a projection" if status == "forecast" else "an estimate"))
    if forced_low or points > c["levels"]["medium"]["max_points"]:
        key = "low"
    elif points > c["levels"]["high"]["max_points"]:
        key = "medium"
    else:
        key = "high"
    return {"level": key, **_lv(c, key), "points": points, "reasons": reasons}


def _lv(c: dict, key: str) -> dict:
    return {"label": c["levels"][key]["label"], "icon": c["levels"][key]["icon"]}


def coverage(years: list[int | None], release_year: int, c: dict | None = None) -> dict:
    """Share of values with data from the last `coverage_recent_years` years."""
    c = c or cfg()
    since = release_year - c["coverage_recent_years"]
    recent = sum(1 for y in years if y is not None and y >= since)
    return {"recent": recent, "of": len(years), "since": since, "share": recent / len(years) if years else 0.0}
