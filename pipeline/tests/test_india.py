"""Indian states: config, name matching and parsing of data.gov.in tables."""
import json

import pytest
import yaml

from pipeline import india
from pipeline.config import DATA


def test_config_has_36_states_and_valid_indicators():
    cfg = yaml.safe_load((DATA / "india_states.yaml").read_text(encoding="utf-8"))
    states = [s for s in cfg["states"] if s["kind"] != "total"]
    states = [s for s in states if s["kind"] != "ignore"]
    assert len(states) == 36 and len({s["id"] for s in states}) == 36
    for ind in cfg["indicators"]:
        assert ind["resource"] and ind["state_field"] and (ind.get("values") or ind.get("sums")), ind["id"]
        assert ind["direction"] in ("higher_better", "lower_better", "neutral")


def test_state_names_match_their_many_spellings():
    i = india.India()
    for name, sid in [("Andaman & Nicobar Islands", "AN"), ("Jammu & Kashmir", "JK"), ("NCT of Delhi", "DL"), ("Orissa", "OD"),
                      ("Uttaranchal", "UK"), ("All India", "IN"), ("Dadra & Nagar Haveli and Daman & Diu", "DH"), ("Tamil Nadu*", "TN")]:
        assert i.match(name) == sid, name


def test_parsing_values_sums_and_periods(tmp_path, monkeypatch):
    monkeypatch.setattr(india, "OUT", tmp_path)
    cfg = yaml.safe_load((DATA / "india_states.yaml").read_text(encoding="utf-8"))
    road = next(x for x in cfg["indicators"] if x["id"] == "road-deaths")
    gsdp = next(x for x in cfg["indicators"] if x["id"] == "gsdp-per-capita")
    names = [s["name"] for s in cfg["states"] if s["kind"] != "total"][:12]
    (tmp_path / f"{road['resource']}.json").write_text(json.dumps({"records": [
        {"state_ut": n, "national_highways__nh____2023": "1,000", "state_highways__sh____2023": "500", "other_roads___2023": "NA",
         "national_highways__nh____2024": "900", "state_highways__sh____2024": "400", "other_roads___2024": "100"} for n in names]}))
    (tmp_path / f"{gsdp['resource']}.json").write_text(json.dumps({"records": [
        {"state": n, "per_capita_gsdp___2019_2020": str(100000 + k), "per_capita_gsdp___2023_24": str(200000 + k)} for k, n in enumerate(names)]}))
    i = india.India()
    assert i.latest("road-deaths", "AP") == ("2024", 1400.0)
    assert i.data["road-deaths"]["AP"][0] == ("2023", 1500.0)          # 'NA' is left out of the sum
    assert i.latest("gsdp-per-capita", "AP")[0] == "2023-24"
    top = i.ranking(next(x for x in i.inds if x["id"] == "gsdp-per-capita"))[0]
    assert top["rank"] == 1 and top["value"] == 200011
    assert india._year("2023-24") == 2024 and india._year("2011") == 2011


def test_snapshot_loads_real_tables_with_all_states_and_no_key():
    from pathlib import Path
    snap = Path(india.SNAPSHOT)
    if not snap.exists():
        pytest.skip("no data/india snapshot")
    for f in snap.iterdir():
        assert "api-key=" not in f.read_text(encoding="utf-8", errors="ignore"), f.name   # the key is never saved
    i = india.India()
    assert len(i.inds) >= 12 and not i.unmatched
    stunting = {r["s"]["id"]: r["value"] for r in i.ranking(next(x for x in i.inds if x["id"] == "stunting"))}
    assert stunting["ML"] > stunting["MN"]                                                   # source swap corrected
