"""Indian states and union territories from data.gov.in (GODL-India).

fetch() runs during the GitHub build with the DATA_GOV_IN_KEY secret; the key is sent only to
api.data.gov.in and never written to disk (saved files record the URL without it). load() turns each
configured table into per-state values, matching the many spellings of state names to one list.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from .config import RAW, load_yaml

API = "https://api.data.gov.in/resource/"
OUT = RAW / "datagovin"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().casefold()
    s = s.replace("&", " and ").replace("*", " ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch(refresh: bool, get, write) -> None:
    """get(url, params) -> response; write(path, bytes, url) records the file and its metadata."""
    key = os.environ.get("DATA_GOV_IN_KEY", "").strip()
    cfg = load_yaml("india_states.yaml")
    if not key:
        print("  data.gov.in: DATA_GOV_IN_KEY not set, skipped")
        return
    for ind in cfg["indicators"]:
        out = OUT / f"{ind['resource']}.json"
        if out.exists() and not refresh:
            continue
        try:
            r = get(API + ind["resource"], {"api-key": key, "format": "json", "limit": 1000, "offset": 0})
            body = r.json()
        except Exception as e:                       # one bad table should not stop the build
            print(f"  data.gov.in {ind['id']}: failed ({type(e).__name__})")
            continue
        records = body.get("records") or []
        payload = {"title": body.get("title"), "updated": body.get("updated_date"), "field": body.get("field"), "records": records}
        write(out, json.dumps(payload).encode(), API + ind["resource"] + "?format=json&limit=1000")   # no key in the record
        print(f"  data.gov.in {ind['id']}: {len(records)} rows")


def _num(v):
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "NA", "N.A.", "na", "..", "*", "#", "N/A"):
        return None
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def _year(label: str) -> int:
    m = re.match(r"(\d{4})(?:-(\d{2,4}))?", label)
    start = int(m.group(1))
    return start + 1 if m.group(2) else start      # a financial or survey year is dated to its end


class India:
    def __init__(self):
        cfg = load_yaml("india_states.yaml")
        self.states = [s for s in cfg["states"] if s["kind"] != "total"]
        self.lookup = {}
        for s in cfg["states"]:
            for n in [s["name"], *s.get("aliases", [])]:
                self.lookup[_norm(n)] = s["id"]
        self.inds, self.data, self.unmatched = [], {}, set()
        for ind in cfg["indicators"]:
            path = OUT / f"{ind['resource']}.json"
            if not path.exists():
                continue
            vals = self._load(ind, json.loads(path.read_text(encoding="utf-8")))
            if sum(1 for k in vals if k != "IN") >= 10:
                self.inds.append(ind)
                self.data[ind["id"]] = vals
        self.by_id = {s["id"]: s for s in cfg["states"]}

    def match(self, name: str):
        k = _norm(name)
        if k in self.lookup:
            return self.lookup[k]
        for n, sid in self.lookup.items():         # e.g. "Jammu & Kashmir #" or trailing notes
            if k.startswith(n) and len(n) > 4:
                return sid
        if k and not k.startswith(("total", "sl", "note", "source")):
            self.unmatched.add(name)
        return None

    def _load(self, ind: dict, payload: dict) -> dict:
        out = {}
        for row in payload.get("records", []):
            sid = self.match(row.get(ind["state_field"], ""))
            if not sid:
                continue
            series = out.setdefault(sid, {})
            for field, label in (ind.get("values") or {}).items():
                v = _num(row.get(field))
                if v is not None:
                    series[str(label)] = v
            for label, fields in (ind.get("sums") or {}).items():
                parts = [_num(row.get(f)) for f in fields]
                if any(p is not None for p in parts):
                    series[str(label)] = sum(p for p in parts if p is not None)
        return {sid: sorted(s.items(), key=lambda kv: _year(kv[0])) for sid, s in out.items() if s}

    # ------------------------------------------------------------------ views
    def latest(self, ind_id: str, sid: str):
        s = self.data.get(ind_id, {}).get(sid)
        return s[-1] if s else None

    def ranking(self, ind: dict) -> list:
        rows = []
        for st in self.states:
            lt = self.latest(ind["id"], st["id"])
            if lt:
                rows.append({"s": st, "period": lt[0], "value": lt[1]})
        rows.sort(key=lambda r: r["value"], reverse=ind["direction"] != "lower_better")
        for k, r in enumerate(rows):
            r["rank"] = k + 1
        peak = max((abs(r["value"]) for r in rows), default=1) or 1
        for r in rows:
            r["bar"] = round(100 * abs(r["value"]) / peak, 1)
        return rows

    def profile(self, sid: str) -> list:
        out = []
        for ind in self.inds:
            series = self.data[ind["id"]].get(sid)
            if not series:
                continue
            rk = next((r for r in self.ranking(ind) if r["s"]["id"] == sid), None)
            nat = self.latest(ind["id"], "IN")
            first = series[0] if len(series) > 1 else None
            out.append({"ind": ind, "period": series[-1][0], "value": series[-1][1], "rank": rk["rank"] if rk else None,
                        "of": len(self.ranking(ind)), "india": nat, "first": first, "series": series})
        return out
