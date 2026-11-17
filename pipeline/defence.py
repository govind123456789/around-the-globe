"""Country defence profiles from the CIA World Factbook (US government work, public domain).

The Factbook's "Military and Security", "Space" and "Terrorism" sections are read from the
factbook.json mirror (a weekly JSON copy of the Factbook). Texts are shown as published, with the
Factbook's own year stamps; military spending (% of GDP) is parsed into numbers for rankings.

Ammunition stocks, weapons counts by type and classified programmes are not published as open
data by any source this site can use, so they are not shown.
"""
from __future__ import annotations

import csv
import html
import json
import re
import zipfile
from pathlib import Path

from .config import RAW

ZIP = RAW / "factbook" / "factbook.zip"
URL = "https://codeload.github.com/factbook/factbook.json/zip/refs/heads/master"
# Factbook (GEC) codes that Wikidata's FIPS map lacks or maps differently
GEC_FIX = {"nl": "NLD", "we": "PSE", "kv": "XKX", "ri": "SRB", "mj": "MNE", "od": "SSD"}
SKIP = {"xx", "ee", "gz", "oo", "zh", "xo", "xq", "zn"}   # world, EU, Gaza (merged into PSE via West Bank), oceans

FIELDS = [("forces", "Military and security forces"), ("personnel", "Military and security service personnel strengths"),
          ("equipment", "Military equipment inventories and acquisitions"), ("service", "Military service age and obligation"),
          ("deployments", "Military deployments"), ("note", "Military - note")]
SPACE = [("agency", "Space agency/agencies"), ("sites", "Space launch site(s)"), ("overview", "Space program overview"),
         ("milestones", "Key space-program milestones")]


def clean(s) -> str:
    """Factbook HTML fragment -> plain text with paragraph breaks."""
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", str(s))
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace(" ", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def paras(s: str) -> list[str]:
    """Paragraphs, each starting with a capital (the Factbook starts most entries in lower case)."""
    return [p[0].upper() + p[1:] for p in (x.strip() for x in re.split(r"\n+", s or "")) if p]


def field(sec: dict, key: str) -> dict | None:
    v = sec.get(key)
    if not isinstance(v, dict):
        return None
    text, note = clean(v.get("text")), clean(v.get("note"))
    if not (text or note):
        return None
    return {"text": paras(text), "note": paras(note)}


def milex(sec: dict) -> list[tuple[int, float]]:
    """[(year, % of GDP)] oldest first."""
    out = {}
    for k, v in (sec.get("Military expenditures") or {}).items():
        y = re.search(r"(\d{4})", k)
        t = v.get("text", "") if isinstance(v, dict) else ""
        m = re.search(r"([\d.]+)% of GDP", t)
        if y and m:
            try:
                out[int(y.group(1))] = float(m.group(1))
            except ValueError:
                pass
    return sorted(out.items())


def service_status(forces: str, service: str) -> str | None:
    """'none' (no standing military), 'conscription' or 'voluntary', read from the Factbook text."""
    f, s = (forces or "").lower(), (service or "").lower()
    if re.search(r"\bno (regular|standing) (military|armed)", f):
        return "none"
    if not s:
        return None
    # drop clauses about conscription that was abolished or suspended
    full = s
    s = "; ".join(c for c in s.split(";") if not re.search(r"abolished|suspended|ended|discontinued", c))
    s = re.sub(r"\b(no|without) (conscription|compulsory \w+ service|draft)", " ", s)
    s = re.sub(r"(compulsory|mandatory) (full-time )?(education|schooling)", " ", s)
    if re.search(r"conscript|\bdraft|compulsory|mandatory|obligatory|obligated to serve", s):
        return "conscription"
    if re.search(r"voluntar|volunteer|enlist|conscription", full):
        return "voluntary"
    return None


def year_of(texts: list[str]) -> int | None:
    ys = [int(y) for t in texts for y in re.findall(r"\((?:\w+\s)?(20\d\d)(?:\s?est\.)?\)", t)]
    return max(ys) if ys else None


def parse(raw: dict) -> dict:
    mil = raw.get("Military and Security") or {}
    out = {k: field(mil, name) for k, name in FIELDS}
    out = {k: v for k, v in out.items() if v}
    out["milex"] = milex(mil)
    sp = raw.get("Space") or {}
    space = {k: field(sp, name) for k, name in SPACE}
    out["space"] = {k: v for k, v in space.items() if v}
    t = field(raw.get("Terrorism") or {}, "Terrorist group(s)")
    out["terror"] = [g.strip() for g in re.split(r";\s*", " ".join(t["text"])) if g.strip()] if t else []
    forces = " ".join((out.get("forces") or {}).get("text", []))
    service = " ".join((out.get("service") or {}).get("text", []))
    out["status"] = service_status(forces, service)
    out["year"] = year_of([forces, service, " ".join((out.get("personnel") or {}).get("text", []))])
    return out


def _fips() -> dict:
    m = {}
    p = RAW / "wikidata" / "fips_iso3.csv"
    if p.exists():
        with open(p, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                m.setdefault(row["fips"].lower(), row["iso3"])
    return m


def load(ids: set, by_name=None, path: Path = ZIP) -> dict:
    """{iso3: profile} for the countries in `ids`. `by_name` resolves a country name when the code map has no entry."""
    if not path.exists():
        return {}
    fips = _fips()
    out = {}
    with zipfile.ZipFile(path) as z:
        for n in sorted(z.namelist()):
            parts = n.split("/")
            if not n.endswith(".json") or len(parts) != 3:
                continue
            gec = parts[-1][:-5]
            if gec in SKIP:
                continue
            raw = json.loads(z.read(n))
            iso = GEC_FIX.get(gec) or fips.get(gec)
            if (not iso or iso not in ids) and by_name:
                nm = clean(((raw.get("Government") or {}).get("Country name") or {}).get("conventional short form", {}).get("text"))
                iso = by_name(nm) if nm and nm.lower() != "none" else None
            if not iso or iso not in ids or iso in out:
                continue
            p = parse(raw)
            if p.get("forces") or p["milex"] or p["space"]:
                p["gec"] = gec
                out[iso] = p
    return out


def summary(profiles: dict, by_id: dict, gdp=None, pop=None) -> dict:
    """Index-page tables: latest spending rankings (share of GDP, US$, per person), service status, space programmes.
    `gdp(iso, year)` and `pop(iso, year)` give World Bank values for the dollar estimates."""
    spend = []
    for iso, p in profiles.items():
        mx = [x for x in p["milex"] if x[0] >= 2022]
        if mx and iso in by_id:
            y, v = mx[-1]
            prev = next((b for a, b in p["milex"] if a == y - 5), p["milex"][0][1] if p["milex"][0][0] < y else None)
            g = gdp(iso, y) if gdp else None
            p = pop(iso, y) if pop else None
            usd = g * v / 100 if g else None
            spend.append({"e": by_id[iso], "year": y, "v": v, "change": (v - prev) if prev is not None else None,
                          "usd": usd, "per": usd / p if usd and p else None})
    spend.sort(key=lambda r: -r["v"])
    for i, r in enumerate(spend, 1):
        r["rank"] = i
    usd = sorted((r for r in spend if r["usd"]), key=lambda r: -r["usd"])
    per = sorted((r for r in spend if r["per"]), key=lambda r: -r["per"])
    status = {k: sorted((by_id[i] for i, p in profiles.items() if p.get("status") == k and i in by_id), key=lambda e: e["name"])
              for k in ("conscription", "voluntary", "none")}
    space = sorted((by_id[i] for i, p in profiles.items() if p["space"].get("agency") and i in by_id), key=lambda e: e["name"])
    return {"spend": spend, "usd": usd, "per": per, "status": status, "space": space, "n": len(profiles),
            "world_usd": sum(r["usd"] for r in usd)}
