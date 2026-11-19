"""Why it moved: every rank change gets one of four causes, in priority order."""
import json

from pipeline import changes


def write_release(root, date, ranking, version, ranks, series):
    d = root / date
    (d / "rankings" / ranking).mkdir(parents=True)
    (d / "rankings" / ranking / f"{version}.json").write_text(json.dumps(
        {"definition": {"indicator": "x"}, "results": [{"entity_id": e, "rank": r} for e, r in ranks.items()]}))
    (d / "indicators").mkdir()
    (d / "indicators" / "x.json").write_text(json.dumps({"data": {e: [[y, v, "measured"] for y, v in s.items()] for e, s in series.items()}}))
    return changes.Release(d)


PREV_SERIES = {"AAA": {2022: 10.0, 2023: 11.0}, "BBB": {2022: 20.0, 2023: 21.0}, "CCC": {2022: 30.0, 2023: 31.0},
               "DDD": {2022: 5.0, 2023: 6.0}}
PREV_RANKS = {"CCC": 1, "BBB": 2, "AAA": 3, "DDD": 4}


def current(ranks, version="1.0.0"):
    return {"r1": {"version": version, "indicator": "x", "definition": {"indicator": "x"},
                   "results": [{"entity_id": e, "rank": r} for e, r in ranks.items()]}}


def test_all_four_causes(tmp_path):
    prev = write_release(tmp_path, "2026-01-01", "r1", "1.0.0", PREV_RANKS, PREV_SERIES)
    cur_series = {"AAA": {2022: 10.0, 2023: 11.0, 2024: 40.0},       # new data year -> moves up
                  "BBB": {2022: 20.0, 2023: 25.0},                   # 2023 revised -> stays the same value order
                  "CCC": {2022: 30.0, 2023: 31.0},                   # unchanged, overtaken -> others
                  "DDD": {2022: 5.0, 2023: 6.0}}
    cur = current({"AAA": 1, "CCC": 2, "BBB": 3, "DDD": 4})
    out = changes.rank_changes(cur, prev, lambda i, e: cur_series.get(e, {}), {"x": {"name": "Thing"}})["r1"]
    assert out["AAA"]["cause"] == "new_year" and out["AAA"]["delta"] == 2 and "new 2024 data" in out["AAA"]["text"]
    assert out["BBB"]["cause"] == "revision" and out["BBB"]["detail"][0]["year"] == 2023
    assert round(out["BBB"]["detail"][0]["pct"], 1) == 19.0 and out["BBB"]["text"].startswith("▼1")
    assert out["CCC"]["cause"] == "others"
    assert "DDD" not in out                                              # no move, no record


def test_method_change_wins(tmp_path):
    prev = write_release(tmp_path, "2026-01-01", "r1", "1.0.0", PREV_RANKS, PREV_SERIES)
    cur = current({"AAA": 1, "CCC": 2, "BBB": 3, "DDD": 4}, version="1.1.0")
    out = changes.rank_changes(cur, prev, lambda i, e: PREV_SERIES.get(e, {}), {})["r1"]
    assert {c["cause"] for c in out.values()} == {"method"}
    noted = changes.rank_changes(current({"AAA": 1, "CCC": 2, "BBB": 3, "DDD": 4}), prev, lambda i, e: PREV_SERIES.get(e, {}), {},
                                 [{"date": "2026-02-01", "ranking": "r1", "note": "new weights"}])["r1"]
    assert all(c["cause"] == "method" and "new weights" in c["text"] for c in noted.values())


def test_same_data_twice_gives_no_changes(tmp_path):
    prev = write_release(tmp_path, "2026-01-01", "r1", "1.0.0", PREV_RANKS, PREV_SERIES)
    assert changes.rank_changes(current(PREV_RANKS), prev, lambda i, e: PREV_SERIES.get(e, {}), {}) == {}


def test_history_appends_and_replaces_same_release():
    h = changes.append_history(None, "2026-01-01", current({"AAA": 2}))
    h = changes.append_history(h, "2026-02-01", current({"AAA": 1}))
    h = changes.append_history(h, "2026-02-01", current({"AAA": 3}))
    assert h["r1"]["AAA"] == [["2026-01-01", 2], ["2026-02-01", 3]]
