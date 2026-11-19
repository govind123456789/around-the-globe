"""Trust levels follow data/trust.yaml; the example old China values score Low."""
from pipeline import trust


def test_old_values_are_low():
    for y in (2000, 2010, 2012):                      # e.g. China youth NEET 2000, primary completion 2010
        assert trust.level("wb-wdi", y, 2026)["level"] == "low"


def test_recent_official_value_is_high_and_estimates_drop():
    assert trust.level("wb-wdi", 2024, 2026)["level"] == "high"
    assert trust.level("wb-wdi", 2024, 2026, "estimate")["level"] == "medium"
    assert trust.level("un-wpp", 2030, 2026, "forecast")["level"] == "low"
    assert trust.level("gdelt", 2026, 2026)["level"] == "medium"


def test_every_indicator_source_is_configured():
    import yaml
    from pipeline.config import DATA
    srcs = {i["source"] for i in yaml.safe_load(open(DATA / "indicators.yaml", encoding="utf-8"))["indicators"]}
    assert srcs <= set(trust.cfg()["sources"])


def test_reasons_explain_the_level():
    r = trust.level("undp-hdr", 2018, 2026, "estimate")
    assert r["level"] == "low" and any("2018" in x for x in r["reasons"])


def test_coverage():
    c = trust.coverage([2024, 2023, 2019, None], 2026)
    assert (c["recent"], c["of"], c["since"]) == (2, 4, 2021)
