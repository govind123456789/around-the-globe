from pipeline import history


def test_wikidata_years_use_astronomical_numbering():
    assert history.wd_year("-0199-01-01T00:00:00Z") == -200      # 200 BCE
    assert history.wd_year("-0001-01-01T00:00:00Z") == -2
    assert history.wd_year("1857-05-10T00:00:00Z") == 1857
    assert history.wd_year("") is None


def test_spans_split_when_share_jumps():
    # Iraq's border overlap with Kuwait (~5%) vs the 1990 occupation (95%)
    series = [(1980, 0.05), (1985, 0.05), (1990, 0.95), (1995, 0.05), (2000, 0.05)]
    assert history.spans(series) == [[1980, 1985, 0.05], [1990, 1990, 0.95], [1995, 2000, 0.05]]


def test_spans_split_on_gaps():
    assert history.spans([(100, 0.5), (105, 0.5), (200, 0.5)]) == [[100, 105, 0.5], [200, 200, 0.5]]


def years(a, b, s):
    return [(y, s) for y in range(a, b + 1, 5)]


def test_stale_colonial_row_after_independence_is_hidden():
    # "France" row still covers Algeria after Algeria's own state appears, and France is based elsewhere
    dza = {"France": years(1900, 2020, 1.0), "Algeria": years(1965, 2024, 0.99) + [(2024, 0.99)]}
    homes = {("France", y): {"FRA", "DZA"} for y in range(1900, 2025, 5)}
    out, removed, names = history.drop_superseded("DZA", dza, homes, end=2024)
    assert max(y for y, _ in out["France"]) < 1965
    assert removed == len([y for y in range(1965, 2021, 5)]) and names == ["France"]


def test_occupation_without_a_concurrent_own_state_is_kept():
    # USSR in Latvia: Latvia's own polity is absent 1940–1990, so nothing is double-counted
    lva = {"USSR": years(1940, 1990, 1.0), "Latvia": years(1920, 1935, 0.98) + years(1995, 2024, 0.98)}
    homes = {("USSR", y): {"RUS", "LVA"} for y in range(1940, 1991, 5)}
    out, removed, _ = history.drop_superseded("LVA", lva, homes, end=2024)
    assert out["USSR"] == lva["USSR"] and removed == 0


def test_regimes_of_the_same_state_are_kept():
    # Francoist Spain overlapping "Kingdom of Spain" is not based in another country
    esp = {"Francoist Spain": years(1940, 1975, 0.98), "Kingdom of Spain": years(1500, 2024, 0.98) + [(2024, 0.98)]}
    homes = {("Francoist Spain", y): {"ESP"} for y in range(1940, 1976, 5)}
    out, removed, _ = history.drop_superseded("ESP", esp, homes, end=2024)
    assert removed == 0 and out["Francoist Spain"] == esp["Francoist Spain"]


def test_short_boundary_overlaps_are_kept():
    nor = {"Nazi Germany": [(1940, 0.8)], "Norway": years(1905, 2024, 0.97) + [(2024, 0.97)]}
    homes = {("Nazi Germany", 1940): {"DEU", "NOR"}}
    _, removed, _ = history.drop_superseded("NOR", nor, homes, end=2024)
    assert removed == 0


def test_manual_keep_override():
    jpn = {"USA": years(1945, 1955, 0.9), "Japan": years(1900, 2024, 0.97) + [(2024, 0.97)]}
    homes = {("USA", y): {"USA", "JPN"} for y in range(1945, 1956, 5)}
    _, removed, _ = history.drop_superseded("JPN", jpn, homes, end=2024, keep_keys=frozenset({"USA"}))
    assert removed == 0
