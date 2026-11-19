"""Why it moved: classify every rank change between the previous data release and this one.

Causes, in priority order (the first that applies wins):
  method    the ranking's version changed, or data/method_changes.yaml has an entry for it since the last release
  revision  a value the ranking uses for this country, for a year present in both releases, changed
  new_year  the country's latest data year for an indicator the ranking uses moved forward
  others    none of the above: the country's own data is unchanged, so other countries moved past it or fell behind

For composite indices the components that changed most are named too.

The previous release is read from its published JSON (rankings/<id>/<version>.json and indicators/<id>.json),
either from dist/v1/releases/<date>/ (local builds) or raw/prev_release/ (CI downloads it from GitHub Releases).
"""
from __future__ import annotations

import json
from pathlib import Path

CAUSES = {"method": "method change", "revision": "data revised", "new_year": "new data year", "others": "other countries moved"}


class Release:
    """Read-only view of a published release directory."""

    def __init__(self, path: Path):
        self.path = Path(path)
        man = self.path / "manifest.json"          # the CI download is not named by date: read it from the manifest
        self.date = json.loads(man.read_text(encoding="utf-8")).get("release", self.path.name) if man.exists() else self.path.name
        self._ind: dict[str, dict] = {}

    def ranking(self, rid: str) -> dict | None:
        d = self.path / "rankings" / rid
        files = sorted(d.glob("*.json")) if d.exists() else []
        if not files:
            return None
        r = json.loads(files[-1].read_text(encoding="utf-8"))
        r["version"] = files[-1].stem
        return r

    def series(self, ind: str, entity: str) -> dict[int, float]:
        if ind not in self._ind:
            p = self.path / "indicators" / f"{ind}.json"
            self._ind[ind] = json.loads(p.read_text(encoding="utf-8")).get("data", {}) if p.exists() else {}
        return {int(y): float(v) for y, v, *_ in self._ind[ind].get(entity, [])}


def previous_release(dist_releases: Path, current: str, fallback: Path | None = None) -> Release | None:
    """The newest release before `current`: locally from dist/v1/releases, else the CI download."""
    if dist_releases.exists():
        older = sorted(p for p in dist_releases.iterdir() if p.is_dir() and p.name < current)
        if older:
            return Release(older[-1])
    if fallback and (fallback / "rankings").exists():
        return Release(fallback)
    return None


def _ranking_indicators(r: dict) -> list[str]:
    d = r.get("definition", {})
    if d.get("pillars"):
        return [i["id"] for p in d["pillars"] for i in p["indicators"]]
    ind = r.get("indicator") or d.get("indicator")
    return [ind] if ind else []


def classify(entity: str, ranking: dict, prev_ranking: dict, cur_series, prev_series, method_note: str | None) -> dict:
    """One rank change. cur_series(ind, entity) / prev_series(ind, entity) -> {year: value}."""
    if method_note or str(ranking.get("version")) != str(prev_ranking.get("version")):
        return {"cause": "method", "detail": method_note or f"version {prev_ranking.get('version')} → {ranking.get('version')}"}
    revised, newer = [], []
    for ind in _ranking_indicators(ranking):
        a, b = prev_series(ind, entity), cur_series(ind, entity)
        common = set(a) & set(b)
        changed = [(y, a[y], b[y]) for y in sorted(common) if abs(a[y] - b[y]) > 1e-9 * max(1.0, abs(a[y]))]
        if changed:
            y, old, new = changed[-1]
            pct = (new - old) / abs(old) * 100 if old else None
            revised.append({"indicator": ind, "year": y, "old": old, "new": new, "pct": pct})
        if a and b and max(b) > max(a):
            newer.append({"indicator": ind, "from": max(a), "to": max(b)})
    if revised:
        return {"cause": "revision", "detail": revised}
    if newer:
        return {"cause": "new_year", "detail": newer}
    return {"cause": "others", "detail": None}


def text(change: dict, indicators: dict) -> str:
    """A short, plain explanation, e.g. "▲3: new 2024 data for life expectancy"."""
    d = change["delta"]
    arrow = f"▲{d}" if d > 0 else f"▼{-d}"
    name = lambda i: (indicators.get(i, {}).get("name") or i)
    c, det = change["cause"], change.get("detail")
    if c == "method":
        return f"{arrow}: method change ({det})"
    if c == "revision":
        parts = [f"{name(x['indicator'])} {x['year']} revised {x['pct']:+.1f}%" if x["pct"] is not None else f"{name(x['indicator'])} {x['year']} revised"
                 for x in det[:2]]
        return f"{arrow}: " + "; ".join(parts)
    if c == "new_year":
        parts = [f"new {x['to']} data for {name(x['indicator']).lower() if not name(x['indicator'])[:2].isupper() else name(x['indicator'])}" for x in det[:2]]
        return f"{arrow}: " + "; ".join(parts)
    return f"{arrow}: own data unchanged; other countries moved"


def rank_changes(rankings: dict, prev: Release, cur_series, indicators: dict, method_changes: list[dict] | None = None) -> dict:
    """{ranking_id: {entity: change}} for every country whose rank differs from the previous release."""
    out: dict[str, dict] = {}
    notes = {}
    for m in method_changes or []:
        if str(m.get("date", "")) > prev.date:
            notes.setdefault(m["ranking"], m.get("note", "method change"))
    for rid, r in rankings.items():
        pr = prev.ranking(rid)
        if not pr:
            continue
        before = {x["entity_id"]: x["rank"] for x in pr.get("results", []) if x.get("rank")}
        changes = {}
        for row in r["results"]:
            e, now = row["entity_id"], row.get("rank")
            if not now or e not in before or before[e] == now:
                continue
            ch = classify(e, r, pr, cur_series, prev.series, notes.get(rid))
            ch.update({"delta": before[e] - now, "from": before[e], "to": now, "prev_release": prev.date})
            ch["text"] = text(ch, indicators)
            changes[e] = ch
        if changes:
            out[rid] = changes
    return out


def append_history(prev_history: dict | None, release: str, rankings: dict) -> dict:
    """Rank history across releases: {ranking: {entity: [[release, rank], ...]}}, kept in every release."""
    h = {k: {e: list(v) for e, v in d.items()} for k, d in (prev_history or {}).items()}
    for rid, r in rankings.items():
        for row in r["results"]:
            if row.get("rank"):
                rows = h.setdefault(rid, {}).setdefault(row["entity_id"], [])
                rows[:] = [x for x in rows if x[0] != release] + [[release, row["rank"]]]
    return h
