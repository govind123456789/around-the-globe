"""Why this rank: explanations built strictly from the computed numbers.

Composite indices (arithmetic): each indicator's points in a country's score are its normalised value times
its effective weight (see engine.contributions); "drivers" compare those points with the median country's
(the same weight times the median normalised value). Positive drivers lift the rank, negative ones hold it back.

Single-indicator rankings: the value, the gap to the country one place above and below, and the rank in each
of the last ten years among countries with data for that exact year.
"""
from __future__ import annotations

from .summaries import ordinal


def drivers(row: dict, indicators: dict, top: int | None = None) -> list[dict]:
    """[{id, name, points}] sorted by size, largest effect first."""
    out = [{"id": k, "name": indicators[k]["name"] if k in indicators else k, "points": v}
           for k, v in (row.get("drivers") or {}).items()]
    out.sort(key=lambda d: -abs(d["points"]))
    return out[:top] if top else out


def _names(ds: list[dict]) -> str:
    names = [f"{d['name'][:1].lower() + d['name'][1:] if not d['name'][:2].isupper() else d['name']} ({d['points']:+.1f})" for d in ds]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def why_sentence(row: dict, ranked_count: int, indicators: dict) -> str:
    """One templated sentence, e.g. "Ranks 4th of 159 mainly because of A (+6.2) and B (+3.1); held back by C (−2.0)." """
    if not row.get("rank") or not row.get("drivers"):
        return ""
    ds = drivers(row, indicators)
    up = [d for d in ds if d["points"] >= 0.5][:2]
    down = [d for d in ds if d["points"] <= -0.5][:2]
    head = f"Ranks {ordinal(row['rank'])} of {ranked_count}"
    if up and down:
        s = f"{head} mainly because of {_names(up)}; held back by {_names(down)}."
    elif up:
        s = f"{head} mainly because of {_names(up)}."
    elif down:
        s = f"{head}, held back mainly by {_names(down)}."
    else:
        s = f"{head}, close to the median country on every component."
    return s


def bars_html(ds: list[dict]) -> str:
    """A diverging bar list (text values included, so it reads without the bars)."""
    if not ds:
        return ""
    peak = max(abs(d["points"]) for d in ds) or 1
    items = []
    for d in ds:
        w = 50 * abs(d["points"]) / peak
        side = "up" if d["points"] >= 0 else "down"
        items.append(f'<li class="{side}"><span class="nm">{_esc(d["name"])}</span><span class="dbar" aria-hidden="true">'
                     f'<i style="width:{w:.1f}%"></i></span><span class="pts">{d["points"]:+.1f}</span></li>')
    return '<ol class="drivers">' + "".join(items) + "</ol>"


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def rank_history(series_by_entity: dict[str, list[tuple[int, float]]], order: str, years: list[int]) -> dict[str, list]:
    """{entity: [[year, rank, of], ...]} ranking only countries with a value for that exact year."""
    out: dict[str, list] = {}
    for y in years:
        vals = [(e, v) for e, ser in series_by_entity.items() for yy, v in ser if yy == y]
        if len(vals) < 10:
            continue
        vals.sort(key=lambda x: x[1], reverse=(order == "desc"))
        n = len(vals)
        for i, (e, _) in enumerate(vals):
            out.setdefault(e, []).append([y, i + 1, n])
    return out


def neighbours(results: list[dict]) -> dict[str, dict]:
    """{entity: {"above": (entity, gap), "below": (entity, gap)}} along the ranked order (gap as a positive number)."""
    ranked = [r for r in results if r.get("rank") and r.get("score") is not None]
    out = {}
    for i, r in enumerate(ranked):
        a = ranked[i - 1] if i > 0 else None
        b = ranked[i + 1] if i + 1 < len(ranked) else None
        out[r["entity_id"]] = {"above": (a["entity_id"], abs(a["score"] - r["score"])) if a else None,
                               "below": (b["entity_id"], abs(r["score"] - b["score"])) if b else None}
    return out
