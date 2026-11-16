"""A World Bank outage must fall back to last week's files instead of failing the weekly build."""
import json

from pipeline import fetch


def test_world_bank_outage_uses_last_weeks_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch, "RAW", tmp_path)
    monkeypatch.setattr(fetch, "WB_PREV", tmp_path / "wb.prev")
    monkeypatch.setattr(fetch, "_wb_failures", 0)
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)
    calls = []

    def down(url, params=None, attempts=5):
        calls.append(url)
        raise RuntimeError("502")
    monkeypatch.setattr(fetch, "_get", down)
    prev = tmp_path / "wb.prev"
    (prev / "licence").mkdir(parents=True)
    for code in ("A.B", "C.D", "E.F", "G.H"):
        (prev / f"{code}.json").write_text(json.dumps({"rows": [code]}))
        (prev / "licence" / f"{code}.json").write_text(json.dumps({"License_Type": "CC BY-4.0"}))
        fetch.fetch_wb_indicator(code, refresh=True)
        assert json.loads((tmp_path / "wb" / f"{code}.json").read_text())["rows"] == [code]
        assert (tmp_path / "wb" / "licence" / f"{code}.json").exists()
    # after three failures in a row the API is treated as down and no longer retried
    assert fetch._wb_down()
    n = len(calls)
    (prev / "I.J.json").write_text("{}")
    (prev / "licence" / "I.J.json").write_text("{}")
    fetch.fetch_wb_indicator("I.J", refresh=True)
    assert len(calls) == n
