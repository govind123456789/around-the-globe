"""Data stories generated from the release, so every figure is computed, not typed.

Each story is a list of blocks rendered by site/templates/story.html. Stories start as
status "draft": the page carries a banner and noindex, and is left out of the sitemap,
until an editor reviews it and sets the status in data/stories.yaml to "published"
(editorial policy: stories are reviewed by a person before publication).
"""
from __future__ import annotations

from . import svg
from .config import load_yaml


def _fmt(v: float, d: int = 0) -> str:
    return f"{v:,.{d}f}"


def the(name: str) -> str:
    """'United States' -> 'the United States' for use mid-sentence."""
    return f"the {name}" if name.startswith(("United ", "Netherlands", "Philippines", "Russian", "Czech")) else name


def _ratio(a: float, b: float) -> str:
    r = a / b
    return f"{r:.1f}" if r < 10 else f"{r:.0f}"


def divergence(site) -> dict:
    countries = [("IND", "s1"), ("CHN", "s2"), ("GBR", "s3"), ("USA", "s4"), ("JPN", "s5")]
    hist = site.hist
    g = {iso: dict((y, v) for y, v in hist[iso]["longrun"]["gdppc"]) for iso, _ in countries}
    name = {iso: site.by_id[iso]["name"] for iso, _ in countries}
    series = [{"label": name[iso], "points": sorted((y, v) for y, v in g[iso].items() if y >= 1500), "cls": cls}
              for iso, cls in countries]
    c1700, b1700 = g["CHN"][1700], g["GBR"][1700]
    c1950, b1950, i1950 = g["CHN"][1950], g["GBR"][1950], g["IND"][1950]
    c22, b22, i22 = g["CHN"][2022], g["GBR"][2022], g["IND"][2022]
    j1950, j1980 = g["JPN"][1950], g["JPN"][1980]
    src = "Maddison Project Database 2023 (Bolt & van Zanden 2024), GDP per capita in 2011 international dollars"
    return {
        "slug": "the-great-divergence", "title": "Two thousand years, one great divergence",
        "dek": "How Asia’s giants fell behind Western Europe and the United States after 1700, and how quickly they are closing the gap.",
        "topics": ["economy", "human"],
        "blocks": [
            ("p", f"In 1700, an average person in China produced about <b>${_fmt(c1700)}</b> a year (in 2011 dollars, adjusted for prices), against "
                  f"<b>${_fmt(b1700)}</b> in Britain: Britain was {_ratio(b1700, c1700)} times richer. "
                  f"By 1950, after the industrial revolution in the West and a century and a half of war, colonisation and upheaval in Asia, "
                  f"the gap had grown to <b>{_ratio(b1950, c1950)} times</b>. Britain stood at ${_fmt(b1950)}, China at ${_fmt(c1950)}, India at ${_fmt(i1950)}."),
            ("chart", svg.line_chart(series, "$", decimals=0, title="GDP per capita since 1500", connect=True, log=True)),
            ("caption", f"GDP per capita since 1500, log scale. Early values are scholarly estimates for benchmark years. Source: {src}."),
            ("h2", "The catch-up"),
            ("p", f"Japan showed first how fast the gap could close: from ${_fmt(j1950)} in 1950 to ${_fmt(j1980)} in 1980, "
                  f"a {_ratio(j1980, j1950)}-fold rise in one generation. China followed from a lower base. Its GDP per capita rose "
                  f"<b>{_ratio(c22, c1950)} times</b> between 1950 and 2022, to ${_fmt(c22)}, and Britain is now only "
                  f"{_ratio(b22, c22)} times richer per person. India’s rise has been slower but has accelerated: "
                  f"<b>{_ratio(i22, i1950)} times</b> since 1950, to ${_fmt(i22)} in 2022, with most of the gain since 1990."),
            ("h2", "What the numbers can’t tell you"),
            ("p", "Estimates before 1820 rest on fragmentary records: wages, prices, harvests and tax returns. They are useful for orders of magnitude, "
                  "not for precise comparisons. GDP per capita also says nothing about how income was shared. "
                  "Explore each country’s full story on its history page, for example "
                  f"<a href=\"/countries/{site.by_id['IND']['slug']}/history/\">India</a> or "
                  f"<a href=\"/countries/{site.by_id['CHN']['slug']}/history/\">China</a>."),
        ],
        "sources": [src],
    }


def ranking_trust(site) -> dict:
    r = site.rk["capability-index"]
    rows = [x for x in r["results"] if x["rank"]]
    n = len(rows)
    width = lambda x: x["rank_high"] - x["rank_low"]
    widths = sorted(width(x) for x in rows)
    median = widths[len(widths) // 2]
    top10 = rows[:10]
    stable = sum(1 for x in top10 if x["rank_high"] <= 10)
    widest = sorted(rows, key=lambda x: (-width(x), x["rank"]))[:6]
    maxw = width(widest[0])
    nm = lambda x: site.by_id[x["entity_id"]]["name"]
    link = lambda x: f'<a href="/countries/{site.by_id[x["entity_id"]]["slug"]}/">{nm(x)}</a>'
    table = [["Country", "Rank", "Range under different weights"]] + [
        [link(x), str(x["rank"]), f'{x["rank_low"]}–{x["rank_high"]}'] for x in widest]
    runs = r["definition"]["mc"]["runs"]
    spread = int(r["definition"]["mc"]["spread"] * 100)
    return {
        "slug": "how-much-to-trust-a-ranking", "title": "How much should you trust a ranking?",
        "dek": "We shook the Capability Index’s weights 1,000 times. The top holds firm; the middle of the table does not.",
        "topics": ["economy", "innovation", "human"],
        "blocks": [
            ("p", "Every composite index rests on choices: which indicators to include and how much each should count. Change the weights and the ranking changes. "
                  "Most rankings publish one order and leave it there. We tested ours instead."),
            ("p", f"For the <a href=\"/rankings/capability-index/\">Capability Index</a>, we recalculated the ranking <b>{runs:,} times</b>, each time moving every weight "
                  f"randomly by up to ±{spread}%. For each of the {n} ranked countries we kept the range that covers the middle 90% of the ranks it got."),
            ("h2", "The top is robust"),
            ("p", f"<b>{stable} of the top 10</b> stayed in the top 10 in at least 95% of the runs. "
                  f"{nm(top10[0])} ranges from {top10[0]['rank_low']} to {top10[0]['rank_high']}, and {nm(top10[8])} from {top10[8]['rank_low']} to {top10[8]['rank_high']}. "
                  "Countries that are strong on every pillar barely move, whatever the weights."),
            ("h2", "The middle is not"),
            ("p", f"The typical country’s range spans <b>{median} places</b>. In the middle of the table, where scores are close together, it spans up to <b>{maxw}</b>. "
                  f"A country there can move {maxw} places on a judgement call about weights, without any change in the underlying data."),
            ("table", table),
            ("caption", f"Countries with the widest 5th–95th percentile rank range in {runs:,} weight perturbations. Capability Index v{r['version']}, release {site.m.release}."),
            ("h2", "What this means"),
            ("p", "Read a mid-table rank as a band, not a position. Each ranking page shows the band next to the rank. "
                  "If you disagree with our weights, set your own in the <a href=\"/index-builder/#from=capability-index\">Index Builder</a>."),
        ],
        "sources": [f"Capability Index v{r['version']} (this site, CC BY 4.0), built from World Bank WDI and UNDP HDR data"],
    }


def news_attention(site) -> dict:
    m = site.m
    pop = {c["entity_id"]: (m.latest(c["entity_id"], "population") or (None, None, None))[1] for c in site.countries}
    world = sum(v for v in pop.values() if v)
    news = {c["entity_id"]: m.latest(c["entity_id"], "news-share") for c in site.countries}
    rows = []
    for iso, lt in news.items():
        if lt and pop.get(iso) and pop[iso] >= 20_000_000:
            ps = 100 * pop[iso] / world
            rows.append({"iso": iso, "news": lt[1], "pop": ps, "ratio": lt[1] / ps, "year": lt[0]})
    rows.sort(key=lambda x: -x["ratio"])
    over, under = rows[:6], sorted(rows, key=lambda x: x["ratio"])[:6]
    nm = lambda iso: site.by_id[iso]["name"]
    link = lambda iso: f'<a href="/countries/{site.by_id[iso]["slug"]}/">{nm(iso)}</a>'
    tab = lambda lst: [["Country", "Share of news", "Share of population", "Ratio"]] + [
        [link(x["iso"]), f'{x["news"]:.2f}%', f'{x["pop"]:.2f}%', f'{x["ratio"]:.1f}×' if x["ratio"] >= 1 else f'{x["ratio"]:.2f}×']
        for x in lst]
    usa = next(x for x in rows if x["iso"] == "USA")
    ind = next(x for x in rows if x["iso"] == "IND")
    top = max(rows, key=lambda x: x["news"])
    under_pop = max(under, key=lambda x: x["pop"])
    return {
        "slug": "who-the-news-is-about", "title": "Who the world’s news is about",
        "dek": f"{the(nm(top['iso']))[:1].upper() + the(nm(top['iso']))[1:]} accounts for {top['news']:.0f}% of global news about events. "
                f"Countries of tens of millions of people, such as {nm(under[0]['iso'])} and {nm(under[2]['iso'])}, barely appear.",
        "topics": ["media"],
        "blocks": [
            ("p", f"Over the last three months, news about events in <b>{the(nm(top['iso']))}</b> made up <b>{top['news']:.1f}%</b> of all the online news articles "
                  f"about events worldwide that the GDELT Project monitors, while it has {top['pop']:.1f}% of the world’s population. "
                  f"India, with {ind['pop']:.1f}% of humanity, had {ind['news']:.1f}% of the coverage. "
                  f"{nm(under_pop['iso'])}, home to {under_pop['pop']:.1f}% of the world’s people, had {under_pop['news']:.2f}%."),
            ("h2", "Most covered, relative to population"),
            ("table", tab(over)),
            ("h2", "Least covered, relative to population"),
            ("table", tab(under)),
            ("caption", f"Countries with at least 20 million people. News share: GDELT 1.0 daily event files, every third day over the last three months (data year {usa['year']}). "
                        f"Population: World Bank WDI, latest year."),
            ("h2", "Why it matters, and the caveats"),
            ("p", "Coverage shapes what readers know and what donors, investors and governments pay attention to. GDELT is the largest open record of global news, "
                  "but it is not neutral: it monitors more English-language and Western outlets, and automated geolocation makes mistakes. "
                  "Read these as broad patterns, not precise measurements. See the full ranking at "
                  "<a href=\"/rankings/news-share/\">most covered in world news</a>."),
        ],
        "sources": ["GDELT Project (gdeltproject.org), open use with citation", "World Bank WDI population (CC BY 4.0)"],
    }


STORIES = [divergence, ranking_trust, news_attention]


def build(site) -> list[dict]:
    status = load_yaml("stories.yaml").get("status", {})
    out = []
    for fn in STORIES:
        s = fn(site)
        s["status"] = status.get(s["slug"], "draft")
        out.append(s)
    return out
