# Launch drafts: Around the Globe

Drafts only: nothing here has been posted or sent. Replace `{SITE}` with the final domain (today:
https://around-the-globe.round-the-globe.workers.dev). Every number below comes from data release 2026-11-10;
re-check them against the live pages before posting.

Facts used:
- 217 countries and territories, 181 indicators, 52 rankings, about 500 country comparison pages.
- Every value carries its source, year, licence and retrieval date, in the page and in the API.
- Data from the World Bank, UNDP, UN population projections, ILO, FAO, Ember, UCDP, UNHCR, the CIA World Factbook and others; green-licence sources only.
- Open API: static JSON under CC BY 4.0, no key needed.

---

## 1. Show HN

**Title:** Show HN: Around the Globe – country rankings where every number shows its source

**Body:**

I built Around the Globe ({SITE}), a free site that ranks and compares 217 countries and territories on 181 indicators, from GDP and life expectancy to electricity, conflict deaths and military spending.

What I wanted, and couldn't find:

- **Per-row sourcing.** Every value shows where it came from, the year it describes, its licence and when it was retrieved. Values older than ten years are greyed out instead of silently mixed in with this year's.
- **Indices you can argue with.** The site has its own composite indices (for example a Capability Index), and each one shows its components, weights and normalisation on the page. The Index Builder lets you change the weights and watch the ranking re-sort in your browser; the link saves your weights.
- **Geopolitics next to economics.** Conflict deaths (UCDP), UN voting alignment, displacement (UNHCR), sanctions, defence profiles and a transparent risk score sit beside the economic and social data, for the same countries.
- **An open API.** The site is built from static JSON files, and those are the API: CC BY 4.0, cross-origin allowed, no key needed.

It's a static Python pipeline that builds about 2,400 pages, deployed on Cloudflare Workers. Only sources whose licences allow reuse are included, and the excluded ones are listed with the reason.

I'd especially like feedback on the methodology pages and on anything that looks wrong; there's an errata page and every correction is logged.

---

## 2. r/dataisbeautiful

**Rules to check before posting:** the [OC] tag needs the source and tool in a top-level comment, and the image should stand on its own.

**Title:** [OC] Military spending as a share of GDP: the biggest five-year rises, to 2024–25

**Chart to export:** the "Biggest rises in five years" list from {SITE}/geopolitics/defence/#spending, as a horizontal bar chart (or a slope chart, from each country's earlier value to its latest).

Values (CIA World Factbook estimates, % of GDP, change over five years):

| Country | Change (points) | Latest |
|---|---|---|
| Israel | +3.0 | 8% (2024) |
| Russia | +3.0 | 7% (2024) |
| Poland | +2.3 | 4.5% (2025) |
| Burkina Faso | +2.1 | 4.5% (2024) |
| Lithuania | +2.0 | 4% (2025) |
| Denmark | +1.9 | 3.2% (2025) |
| Norway | +1.7 | 3.4% (2025) |
| Qatar | +1.6 | 5% (2023) |
| Latvia | +1.5 | 3.7% (2025) |
| Luxembourg | +1.5 | 2% (2025) |

**Top-level comment:**

Source: CIA World Factbook (public domain), military expenditure as a share of GDP, latest estimate for each country since 2022, compared with five years earlier. Years differ between countries and are shown. Tool: Around the Globe ({SITE}), a free open-data site; the full list of 153 countries, plus profiles for each country's forces, equipment and service rules, is at {SITE}/geopolitics/defence/. These are estimates: the Factbook doesn't publish spending in money, and SIPRI's figures aren't reusable here.

---

## 3. LinkedIn

Most country rankings ask you to trust them. I wanted one that shows its work.

Around the Globe ({SITE}) is a free, open-data site that compares 217 countries and territories on 181 indicators. What's different:

→ Every number shows its source, its year and its licence, right next to the value.
→ Composite indices publish their weights, and the Index Builder lets you change them and watch the ranking re-sort.
→ Geopolitics (conflict, UN votes, displacement, sanctions, defence) sits alongside the economic and social data, for the same countries.
→ Everything is available as an open API under CC BY 4.0, with no key needed.

If you work with country data, as an analyst, journalist, teacher or student, I'd value your feedback, especially on what's missing or wrong.

#OpenData #DataVisualization #Geopolitics

---

## 4. Email pitch to data journalists and educators

**Subject:** A free country-data site where every number is sourced and dated

Hi {Name},

I've built Around the Globe ({SITE}), a free site that ranks and compares 217 countries and territories on 181 indicators, and I think it could save you time when you need a quick, citable country figure.

Three things set it apart:

1. **Every value is sourced and dated** on the page: publisher, the year the figure describes, licence and retrieval date. Old figures are flagged rather than mixed in.
2. **Comparisons are ready to use**: about 500 side-by-side pages (for example {SITE}/compare/china-vs-india/), each with the method written out, plus an Index Builder for classes or stories that need their own weighting.
3. **It's open**: the data is CC BY 4.0, with bulk downloads and a JSON API, no sign-up needed.

It also covers geopolitics alongside economics: conflict deaths, UN voting alignment, displacement and defence profiles, for the same countries.

If it's useful, I'd love to hear what you'd need from it. Corrections are welcome and are logged publicly.

Best,
{Your name}

---

## Before posting

- Confirm the final domain, then update `base_url` and the contact email in `data/site.yaml`.
- Re-check every number above against the live pages after the next data release.
- For Reddit, export the chart as a PNG with the source line in the image.
