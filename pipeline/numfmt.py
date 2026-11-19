"""One number formatter for the whole site (Python side; site/static/js/numfmt.js mirrors it in the browser).

value(v, decimals, unit)  full value for tables and text: thousands separators, the indicator's decimals,
                          large numbers as "1.46 bn", US dollars with "$". (The rules the site always used,
                          moved here unchanged, so no published number changes.)
scale(v, decimals)        large numbers in words: "1.46 bn", "312 m", "45k"; chart axes and labels.
compact(v, unit)          tiles: 1.4B, 312M, $12.3k, 7.1%.
The unit is always shown: money and percentages carry their symbol in compact(); elsewhere the templates
add the unit (unit_short) or the label names it.
"""
from __future__ import annotations

import math


def scale(v: float, decimals: int = 1) -> str:
    a = abs(v)
    if a == 0:
        return "0"
    for div, suf in ((1e12, " tn"), (1e9, " bn"), (1e6, " m"), (1e4, "k")):
        if a >= div:
            if suf == "k":
                return f"{v/1e3:,.0f}k"
            return f"{v/div:,.{decimals}f}{suf}"
    if a >= 100:
        return f"{v:,.0f}"
    return f"{v:,.{decimals}f}"


def value(v, decimals: int = 2, unit: str = "") -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e6:
        s = scale(v, 2 if abs(v) < 1e10 else 1)
    else:
        s = f"{v:,.{decimals}f}"
    if unit.startswith("current US$") and not unit.endswith("person"):
        s = "$" + s
    return s


def _money(unit: str) -> bool:
    u = unit or ""
    return "US$" in u or u.startswith("$") or "international $" in u


def compact(v, unit: str = "", decimals: int | None = None) -> str:
    """Short form for tiles: 1.4B, 312M, $12.3k, 7.1%."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    a = abs(v)
    sign = "−" if v < 0 else ""
    if (unit or "").startswith("%"):
        d = 1 if decimals is None else min(decimals, 1)
        return f"{sign}{a:.{d}f}%"
    money = "$" if _money(unit) else ""
    for size, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "k")):
        if a >= size:
            n = a / size
            txt = f"{n:.0f}" if n >= 100 else f"{n:.1f}".rstrip("0").rstrip(".")
            return f"{sign}{money}{txt}{suf}"
    if decimals is None:
        decimals = 0 if a >= 100 else 1 if a >= 10 else 2
    return f"{sign}{money}{a:,.{decimals}f}"
