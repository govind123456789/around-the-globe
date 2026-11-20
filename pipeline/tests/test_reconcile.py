"""Sources compared: the primary value is untouched; the alternative is matched on year and flagged by threshold."""
from pipeline import reconcile


class M:
    def __init__(self, s):
        self.s = s

    def series(self, e, ind):
        return [(y, v, "measured") for y, v in self.s.get(e, {}).items()]


def test_compare_matches_year_and_ignores_projections():
    m = M({"AAA": {2022: 100.0, 2023: 110.0}})
    alt = {"population": {"AAA": {2022: (102.0, "measured"), 2023: (121.0, "measured"), 2024: (130.0, "forecast")}}}
    c = reconcile.compare(m, "population", "AAA", alt)
    assert c["year"] == 2023 and c["primary"] == 110.0 and round(c["diff"], 1) == 10.0
    assert reconcile.compare(m, "population", "ZZZ", alt) is None


def test_table_flags_beyond_threshold_and_sorts():
    m = M({"AAA": {2023: 100.0}, "BBB": {2023: 100.0}})
    alt = {"population": {"AAA": {2023: (103.0, "measured")}, "BBB": {2023: (90.0, "measured")}}}
    t = reconcile.table(m, "population", alt, ["AAA", "BBB"], 5)
    assert [r["iso"] for r in t] == ["BBB", "AAA"] and t[0]["flag"] and not t[1]["flag"]


def test_config_has_explanations():
    c = reconcile.cfg()
    assert c["threshold_pct"] > 0 and all(v["why"] and v["alt_source"] for v in c["indicators"].values())
