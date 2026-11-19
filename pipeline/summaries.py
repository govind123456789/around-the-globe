"""Short, factual summaries at the top of country, indicator and comparison pages.

Every sentence is built from the dataset at build time: each number is a published value or a rank
computed by this site, and each comes with its year. Nothing is interpretive: no "strong", "weak",
"impressive" or causes. A sentence is left out when its data is missing.
"""
from __future__ import annotations

from statistics import median


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def say(v: float, ind: dict, fmt) -> str:
    """A value with its unit, readable inside a sentence."""
    unit = ind.get("unit", "")
    n = fmt(v, ind.get("decimals", 1), unit)
    if "$" in unit:
        if "$" not in n:
            n = "$" + n
        return n + (" (PPP)" if "PPP" in unit else "")
    if unit.startswith("%"):
        return n + unit
    if unit.startswith("index") or unit in ("", "score", "score (0–100)"):
        return n
    return f"{n} {unit}"


def _row(rankings: dict, rid: str, eid: str):
    r = rankings.get(rid)
    if not r:
        return None, None
    row = next((x for x in r["results"] if x["entity_id"] == eid), None)
    return r, row


def _rank_phrase(r: dict, row: dict) -> str:
    return f"{ordinal(row['rank'])} of {r['ranked_count']}"


def country(e: dict, rankings: dict, indicators: dict, fmt) -> list[str]:
    name = e["name"]
    out = []
    parts = []
    for rid, label in (("gdp-per-capita-ppp", "GDP per person (PPP)"), ("life-expectancy", "life expectancy")):
        r, row = _row(rankings, rid, e["entity_id"])
        if row and row.get("rank") and row.get("year") and r.get("indicator") in indicators:
            parts.append(f"{label} is {say(row['score'], indicators[r['indicator']], fmt)} ({row['year']}), "
                         f"{_rank_phrase(r, row)} countries and territories")
    if parts:
        out.append(f"{name}’s " + "; its ".join(parts) + ".")
    r, row = _row(rankings, "population", e["entity_id"])
    if row and row.get("rank") and row.get("year"):
        place = ("the largest" if row["rank"] == 1 else "the smallest" if row["rank"] == r["ranked_count"]
                 else f"the {ordinal(row['rank'])} largest")
        out.append(f"Its population is {say(row['score'], indicators['population'], fmt)} ({row['year']}), "
                   f"{place} of {r['ranked_count']}.")
    r, row = _row(rankings, "capability-index", e["entity_id"])
    if row and row.get("rank"):
        out.append(f"On this site’s Capability Index, an original index rather than an official statistic, it ranks "
                   f"{_rank_phrase(r, row)} with a score of {row['score']:.1f} out of 100.")
    return out


def indicator(ind: dict, latest: list[dict], fmt, world=None) -> list[str]:
    """`latest`: [{"e": entity, "value": v, "year": y}] for countries; `world`: (year, value) or None."""
    if not latest:
        return []
    vals = sorted(latest, key=lambda x: x["value"])
    lo, hi = vals[0], vals[-1]
    med = median(x["value"] for x in vals)
    years = sorted({x["year"] for x in vals})
    yr = f"{years[0]}" if len(years) == 1 else f"{years[0]}–{years[-1]}"
    out = [f"{len(vals)} countries and territories have data on {ind['name'][:1].lower() + ind['name'][1:] if not ind['name'][:2].isupper() else ind['name']}, "
           f"with latest values from {yr}."]
    if len(vals) > 1:
        out.append(f"The highest is {hi['e']['name']} at {say(hi['value'], ind, fmt)} ({hi['year']}) and the lowest "
                   f"{lo['e']['name']} at {say(lo['value'], ind, fmt)} ({lo['year']}); the median is {say(med, ind, fmt)}.")
    if world:
        out.append(f"The world figure is {say(world[1], ind, fmt)} ({world[0]}).")
    return out


def pair(a: dict, b: dict, rankings: dict, indicators: dict, fmt) -> list[str]:
    out = []
    for rid, label in (("gdp-per-capita-ppp", "GDP per person (PPP)"), ("life-expectancy", "Life expectancy")):
        r, ra = _row(rankings, rid, a["entity_id"])
        _, rb = _row(rankings, rid, b["entity_id"])
        if not (ra and rb and ra.get("rank") and rb.get("rank") and r.get("indicator") in indicators):
            continue
        ind = indicators[r["indicator"]]
        out.append(f"{label}: {a['name']} {say(ra['score'], ind, fmt)} ({ra['year']}, {_rank_phrase(r, ra)}); "
                   f"{b['name']} {say(rb['score'], ind, fmt)} ({rb['year']}, {_rank_phrase(r, rb)}).")
    wins_a = wins_b = both = 0
    for r in rankings.values():
        ra = next((x for x in r["results"] if x["entity_id"] == a["entity_id"]), None)
        rb = next((x for x in r["results"] if x["entity_id"] == b["entity_id"]), None)
        if ra and rb and ra.get("rank") and rb.get("rank"):
            both += 1
            if ra["rank"] < rb["rank"]:
                wins_a += 1
            elif rb["rank"] < ra["rank"]:
                wins_b += 1
    if both:
        out.append(f"Of the {both} rankings on this site that include both, {a['name']} places higher in {wins_a} and "
                   f"{b['name']} in {wins_b}{'' if wins_a + wins_b == both else ', with ' + str(both - wins_a - wins_b) + ' tied'}.")
    return out
