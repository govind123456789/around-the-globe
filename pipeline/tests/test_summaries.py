"""Generated summaries: every number comes from the data passed in, with its year."""
import re

from pipeline import summaries


def fmt(v, d=1, unit=""):
    return f"{v:,.{d}f}"


IND = {"gdp-per-capita-ppp": {"unit": "current international $ (PPP)", "decimals": 0, "name": "GDP per capita, PPP"},
       "life-expectancy": {"unit": "years", "decimals": 1, "name": "Life expectancy"},
       "population": {"unit": "people", "decimals": 0, "name": "Population"}}


def rk(rid, ind, rows):
    return {"indicator": ind, "ranked_count": len(rows), "kind": "single_indicator",
            "results": [{"entity_id": e, "rank": i + 1, "score": v, "year": y} for i, (e, v, y) in enumerate(rows)]}


RANKS = {"gdp-per-capita-ppp": rk("g", "gdp-per-capita-ppp", [("AAA", 50000, 2024), ("BBB", 20000, 2023)]),
         "life-expectancy": rk("l", "life-expectancy", [("BBB", 80.0, 2023), ("AAA", 75.5, 2022)]),
         "population": rk("p", "population", [("AAA", 9000, 2024), ("BBB", 100, 2024)])}
A, B = {"entity_id": "AAA", "name": "Aland"}, {"entity_id": "BBB", "name": "Bland"}


def numbers(text):
    return {x.replace(",", "") for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def test_country_summary_uses_only_given_numbers_and_years():
    text = " ".join(summaries.country(A, RANKS, IND, fmt))
    assert "50,000" in text and "(2024)" in text and "75.5" in text and "(2022)" in text
    assert "the largest of 2" in text
    assert numbers(text) <= {"50000", "2024", "1", "2", "75.5", "2022", "9000"} | {"1st", "2nd"}
    assert "the smallest of 2" in " ".join(summaries.country(B, RANKS, IND, fmt))


def test_pair_summary_counts_rankings():
    text = " ".join(summaries.pair(A, B, RANKS, IND, fmt))
    assert "Of the 3 rankings" in text and "Aland places higher in 2" in text and "Bland in 1" in text


def test_missing_data_drops_sentences():
    assert summaries.country({"entity_id": "ZZZ", "name": "Zed"}, RANKS, IND, fmt) == []
    assert summaries.indicator(IND["population"], [], fmt) == []
