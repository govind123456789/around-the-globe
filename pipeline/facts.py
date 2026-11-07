"""Basic country facts from Wikidata (CC0), cleaned for display.

Wikidata is community-maintained, so values are filtered here and corrected in
data/country_facts_overrides.yaml. Area comes from the World Bank, not from here.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from .config import RAW, load_yaml

FACTS_DIR = RAW / "wikidata" / "facts"
QID = re.compile(r"Q\d+")
LATIN_DOMAIN = re.compile(r"\.[a-z]{2,}")


def _rows(name: str, known: set[str], facts_dir: Path) -> dict[str, set[tuple[str, str]]]:
    """iso3 -> {(label, extra)}. Merges duplicate Wikidata items for one code (e.g. Palestine)."""
    out: dict[str, set[tuple[str, str]]] = {}
    path = facts_dir / f"{name}.csv"
    if not path.exists():
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["iso3"] in known and not QID.fullmatch(r["vLabel"]):
                out.setdefault(r["iso3"], set()).add((r["vLabel"], r.get("extra") or ""))
    return out


def clean_highest(values: set[tuple[str, str]]) -> dict | None:
    """Highest listed elevation wins; ties go alphabetically, so the result is stable."""
    def elevation(extra: str) -> float:
        try:
            return float(extra)
        except ValueError:
            return -1.0
    name, extra = sorted(values, key=lambda x: (-elevation(x[1]), x[0]))[0]
    return {"name": name, "elevation_m": round(float(extra)) if elevation(extra) >= 0 else None}


def clean_currency(values: set[tuple[str, str]]) -> list[dict]:
    """One entry per ISO code. Currencies without a code are kept under their name."""
    by_key: dict[str, dict] = {}
    for name, code in sorted(values):
        by_key.setdefault(code or name, {"name": name, "code": code or None})
    return sorted(by_key.values(), key=lambda c: c["name"].casefold())


def symmetric_borders(raw: dict[str, set[tuple[str, str]]], known: set[str]) -> dict[str, set[str]]:
    """Wikidata lists many borders on one side only. A border belongs to both countries."""
    out: dict[str, set[str]] = {}
    for iso, values in raw.items():
        for _, other in values:
            if other in known and other != iso:
                out.setdefault(iso, set()).add(other)
                out.setdefault(other, set()).add(iso)
    return out


def load(entities: dict[str, dict], facts_dir: Path = FACTS_DIR, overrides: dict | None = None) -> dict[str, dict]:
    """iso3 -> facts, for every country. Countries without data get an empty dict."""
    names = {k: v for k, v in entities.items() if v["type"] == "country"}
    known = set(names)
    if overrides is None:
        overrides = load_yaml("country_facts_overrides.yaml")["overrides"]
    languages = _rows("languages", known, facts_dir)
    currency = _rows("currency", known, facts_dir)
    calling = _rows("calling_code", known, facts_dir)
    domains = _rows("internet_domain", known, facts_dir)
    drives = _rows("drives_on", known, facts_dir)
    highest = _rows("highest_point", known, facts_dir)
    borders = symmetric_borders(_rows("neighbours", known, facts_dir), known)

    out: dict[str, dict] = {}
    for iso in names:
        f: dict = {}
        if iso in languages:
            f["languages"] = sorted({x[0] for x in languages[iso]}, key=str.casefold)
        if iso in currency:
            f["currency"] = clean_currency(currency[iso])
        if iso in calling:
            f["calling_code"] = sorted({x[0] for x in calling[iso]})
        if iso in domains:
            kept = sorted(x[0] for x in domains[iso] if LATIN_DOMAIN.fullmatch(x[0]))
            if kept:
                f["internet_domain"] = kept
        if iso in drives:
            f["drives_on"] = sorted(x[0] for x in drives[iso])[0]
        if iso in highest:
            f["highest_point"] = clean_highest(highest[iso])
        f.update(overrides.get(iso, {}))
        if iso in borders:
            members = sorted(borders[iso], key=lambda b: names[b]["name"].casefold())
            f["borders"] = [{"entity_id": b, "name": names[b]["name"], "slug": names[b]["slug"]} for b in members]
        out[iso] = f
    return out
