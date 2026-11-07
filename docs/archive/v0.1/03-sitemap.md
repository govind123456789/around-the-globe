# Sitemap & URL scheme

Legend: **[MVP]** months 1–4 · **[M5-6]** intelligence layer · **[M7-9]** entity expansion · **[M10-12]** monetization. Every page is server-rendered with a stable canonical URL.

## Top-level navigation
`Explore · Rankings · Compare · Topics · Insights · Index Builder · Data`

## Full tree

```
/                                             Home — search, featured rankings, map, insights            [MVP]
│
├── /explore                                  World map + featured topics + what's new                   [MVP]
│
├── /rankings                                 Browse/filter all rankings (type, topic, kind)             [MVP]
│   ├── /rankings/{ranking-slug}              Current edition                                             [MVP]
│   │     ?edition={version}                  Past edition (canonical stays on slug + edition param)    [MVP]
│   │     ?view=map|table   ?region=   ?income=   ?min_coverage=
│   ├── /rankings/{ranking-slug}/history      Rank movement over editions                                 [MVP]
│   └── /rankings/{ranking-slug}/sensitivity  Weight-perturbation results                                 [MVP]
│
├── /countries                                A–Z, by region, by income group                            [MVP]
│   ├── /countries/{country-slug}             Country profile                                             [MVP]
│   ├── /countries/{country-slug}/{dimension} Dimension deep-dive (economy, health …)                     [MVP]
│   └── /countries/{country-slug}/rankings    Every ranking this country appears in                      [MVP]
├── /regions/{group-slug}                     Region / income-group aggregate profile                     [MVP]
├── /cities/{city-slug}                       City profile                                                [M7-9]
├── /universities/{university-slug}           University profile                                          [M7-9]
├── /companies/{company-slug}                 Company profile                                             [M10-12]
├── /industries/{industry-slug}               Industry profile                                            [M10-12]
│
├── /compare                                  Compare builder (pick type + entities)                     [MVP]
│   └── /compare/{a}-vs-{b}[-vs-{c}…]         Canonical comparison (slugs sorted A–Z; others 301)        [MVP]
│         ?ranking={slug}  ?indicators=a,b,c
│
├── /topics                                   All topics                                                  [MVP]
│   └── /topics/{topic-slug}                  Topic hub: rankings, indicators, insights                  [MVP]
│
├── /insights                                 Reports listing                                             [MVP: 3 pieces]
│   ├── /insights/{report-slug}               Analysis report                                             [MVP]
│   ├── /insights/trends                      Auto-detected anomalies (statistically flagged)            [M5-6]
│   └── /insights/newsletter                  Newsletter archive + signup                                 [M7-9]
│
├── /index-builder                            Builder landing / templates                                [M5-6]
│   ├── /index-builder/new                    Builder workspace                                           [M5-6]
│   └── /index-builder/{share-slug}           Shared custom index (noindex unless published)             [M5-6]
│
├── /ask                                      AI research (evidence-linked answers)                      [M5-6]
│   └── /ask/{answer-id}                      Permalink to an answer + trace                              [M5-6]
│
├── /data                                     Data explorer landing                                       [MVP]
│   ├── /data/indicators                      Indicator catalogue (filter by dimension, source)          [MVP]
│   ├── /data/indicators/{indicator-slug}     Indicator page: definition, map, series, download          [MVP]
│   ├── /data/sources                         Sources directory with licences                             [MVP]
│   ├── /data/sources/{source-slug}           Source detail + release history                             [MVP]
│   ├── /data/downloads                       Bulk edition downloads (licence-permitting)                [M7-9]
│   └── /data/api                             API docs (rendered from OpenAPI)                            [M10-12]
│
├── /methodology                              Principles: observed vs calculated vs interpretation       [MVP]
│   └── /methodology/{ranking-slug}           Methodology for current version                             [MVP]
│         ?version={version}
│
├── /account …                                Sign-in, saved views, billing                               [M7-9 / M10-12]
├── /pricing                                                                                              [M10-12]
├── /embed/{chart-type}/{…}                   Iframe-embeddable charts (noindex, canonical → source)     [M7-9]
│
└── /about  /about/editorial-policy  /about/corrections  /contact  /privacy  /terms                      [MVP]
```

## URL rules

1. Slugs are lowercase ASCII, hyphenated, and permanent. Renames add a 301 from the old slug (`entity_aliases` / redirect table).
2. Entity type is in the path (`/countries/…`, `/cities/…`) so `georgia` the country and `georgia` the US state never collide.
3. Comparison URLs are canonicalised: `/compare/india-vs-china` 301s to `/compare/china-vs-india`. Max 5 entities.
4. Filters are query params and do not create new canonicals (`rel=canonical` → base URL).
5. User-generated pages (custom indices, AI answers) are `noindex` until an editor publishes them.
6. `sitemap.xml` is generated from the database: rankings, entities, indicators, methodology, insights. Comparison pages are included only for a curated list (top pairs by search demand once measured), not every combination.

## Launch page count estimate (MVP)

| Template | Count |
|---|---|
| Country profiles | ~217 |
| Region / income-group profiles | ~15 |
| Ranking pages | ~12 |
| Methodology pages | ~12 |
| Indicator pages | 30–50 |
| Topic hubs | ~8 |
| Curated comparison pages in sitemap | ~50 |
| Insights | 3 |
| Static pages | ~8 |
