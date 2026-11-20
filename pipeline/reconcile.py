"""Sources compared: the World Bank's value beside another major source's for the same country and year.

Primary values and rankings are never changed. For each configured indicator (data/reconciliation.yaml) the
alternative series is read with its own provenance, matched on year, and the difference from the primary
value is computed. Countries beyond the threshold are flagged "sources disagree".
"""
from __future__ import annotations

import csv
import gzip

from .config import RAW, load_yaml

WPP = RAW / "un" / "wpp2024_demographic_indicators.csv.gz"


def cfg() -> dict:
    return load_yaml("reconciliation.yaml")


def load_alt(c: dict, ids: set) -> dict:
    """{indicator: {iso: {year: (value, status)}}} from the alternative source files."""
    out = {k: {} for k in c["indicators"]}
    if not WPP.exists():
        return out
    wanted = {k: v for k, v in c["indicators"].items() if v["alt_source"] == "un-wpp"}
    with gzip.open(WPP, "rt", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            iso = row["ISO3_code"]
            if iso not in ids:
                continue
            y = int(row["Time"])
            if y < 1990 or y > 2030:
                continue
            for k, v in wanted.items():
                raw = row.get(v["alt_field"])
                if raw:
                    status = "measured" if y <= v["estimates_until"] else "forecast"
                    out[k].setdefault(iso, {})[y] = (float(raw) * v["alt_scale"], status)
    return out


def compare(model, ind: str, iso: str, alt: dict) -> dict | None:
    """The latest year both sources have: primary value, alternative value, % difference, and both series."""
    prim = {y: v for y, v, _ in model.series(iso, ind)}
    other = alt.get(ind, {}).get(iso, {})
    common = sorted(set(prim) & {y for y, (_, st) in other.items() if st == "measured"})
    if not common:
        return None
    y = common[-1]
    p, a = prim[y], other[y][0]
    diff = (a - p) / abs(p) * 100 if p else None
    return {"year": y, "primary": p, "alt": a, "diff": diff,
            "series": [[(yy, prim[yy]) for yy in sorted(prim) if yy >= 2000],
                       [(yy, v) for yy, (v, st) in sorted(other.items()) if 2000 <= yy <= max(prim) and st == "measured"]]}


def table(model, ind: str, alt: dict, ids: list[str], threshold: float) -> list[dict]:
    """Every country with both sources, largest disagreement first."""
    rows = []
    for iso in ids:
        c = compare(model, ind, iso, alt)
        if c and c["diff"] is not None:
            rows.append({"iso": iso, **c, "flag": abs(c["diff"]) > threshold})
    rows.sort(key=lambda r: -abs(r["diff"]))
    return rows
