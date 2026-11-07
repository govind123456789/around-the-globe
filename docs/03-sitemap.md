# Sitemap & URL scheme (v0.2: static)

Legend: **[v1]** launch (~week 16) · **[M5-6]** AI + distribution · **[M7-12]** expansion · **[M13-24]** sustain.
Every page is a static file built from the release JSON. **Pre-rendered** = HTML at build time (indexable). **Client** = one template page that fetches JSON from R2 (`noindex`).

The Workers Free plan holds 20,000 static files. At launch the site has roughly 400 pages plus about 1,000 JSON files on R2 (R2 files don't count). Universities (tens of thousands) will use a client template + R2 JSON, or Workers Paid.

## Top-level navigation
`Explore · Rankings · Compare · Topics · Insights · Index Builder · Data`

## Tree

```
/                                             Home                                                      [v1] pre-rendered
├── /explore                                  World map + featured topics + what's new                  [v1] pre-rendered
│
├── /rankings                                 All rankings                                              [v1] pre-rendered
│   ├── /rankings/{ranking-slug}              Current edition                                           [v1] pre-rendered
│   ├── /rankings/{ranking-slug}/{version}    Past edition (immutable)                                  [v1] pre-rendered
│   ├── /rankings/{ranking-slug}/history      Rank over editions                                        [v1] pre-rendered
│   └── /rankings/{ranking-slug}/sensitivity  Monte Carlo rank bands + "try other weights"              [v1] pre-rendered
│
├── /countries                                A–Z, by region, by income group                          [v1] pre-rendered
│   └── /countries/{country-slug}             Country profile (incl. batch AI summary in M5-6)         [v1] pre-rendered
├── /regions/{group-slug}                     Region / income-group profile                             [v1] pre-rendered
├── /universities/{slug}                      OpenAlex / Leiden-based profile                           [M7-12] client template
├── /cities/{slug}                            GHSL city layer (beta)                                    [M7-12] client template
├── /companies/{slug}                         EDGAR / GLEIF / Wikidata                                  [M13-24] client template
│
├── /compare                                  Compare builder                                           [v1] pre-rendered shell
│   ├── /compare/{a}-vs-{b}                   Curated popular pairs only (slugs sorted A–Z)            [v1] pre-rendered
│   └── /compare#c=IND,CHN,VNM&i=…            Any other combination                                    [v1] client, noindex
│
├── /topics/{topic-slug}                      Topic hub                                                 [v1] pre-rendered
│
├── /insights                                 Data stories (3 at launch)                                [v1] pre-rendered
│   ├── /insights/{slug}                      Story                                                     [v1]
│   └── /insights/releases/{date}             Release notes: what changed vs last edition              [v1] generated
│
├── /index-builder                            Builder (state in URL fragment)                           [v1] client
│   └── /index-builder/templates/{slug}       Study abroad · Market entry · Relocation                 [M5-6]
│
├── /ask                                      Live AI assistant (quota-limited)                         [M5-6] client → Worker
│
├── /data                                     Data hub                                                  [v1]
│   ├── /data/indicators                      Indicator catalogue                                       [v1] pre-rendered
│   ├── /data/indicators/{indicator-slug}     Indicator page                                            [v1] pre-rendered
│   ├── /data/sources                         Sources + licence tier + attribution                     [v1] pre-rendered
│   ├── /data/downloads                       Bulk CSV/Parquet per release, LICENSE + ATTRIBUTION      [v1]
│   ├── /data/api                             Static JSON API docs (from 05-openapi.yaml)              [v1]
│   ├── /data/mcp                             MCP server docs                                           [M5-6]
│   └── /data/explorer                        DuckDB-WASM SQL over Parquet (lazy-loaded)               [M5-6] client
│
├── /methodology                              Principles: observed vs calculated vs interpretation     [v1]
│   └── /methodology/{ranking-slug}/{version} Methodology per version                                  [v1]
│
├── /embed/{chart}/{…}                        Iframe charts with attribution + backlink                [M5-6] noindex
│
└── /about                                                                                              [v1]
    ├── /about/editorial-policy               Independence + conflict-of-interest                     [v1]
    ├── /about/errata                         Corrections log                                          [v1]
    ├── /about/licences                       CC BY 4.0 data · AGPL/MIT code · how to cite             [v1]
    ├── /about/funding                        Who pays; 60% single-funder cap                          [v1]
    ├── /about/donate                         Donation page                                             [M5-6]
    └── /about/privacy                        No accounts, cookieless analytics                        [v1]
```

Removed from v0.1: `/pricing`, `/account/*`, saved-view pages, `/ask/{answer-id}` permalinks (would need server storage).

## URL rules

1. Slugs are lowercase ASCII, hyphenated and permanent; renames get a static redirect (`_redirects`).
2. Entity type is in the path, so a country and a US state named Georgia never collide.
3. Only curated compare pairs get indexable URLs. Other combinations live in the URL fragment (`#c=…`), so they are never separate pages.
4. Index Builder and Compare state goes in the fragment and never reaches a server.
5. `sitemap.xml` is generated at build from the release: rankings, editions, countries, indicators, methodology, insights, curated pairs.

## v1 page count estimate

| Template | Count |
|---|---|
| Country profiles | ~200 |
| Region / income-group profiles | ~15 |
| Rankings × (current + history + sensitivity) | ~12 × 3 |
| Methodology pages | ~12 |
| Indicator pages | 40–60 |
| Topic hubs | ~8 |
| Curated compare pairs | ~50 |
| Insights + release notes | ~5 |
| Static / about | ~10 |
| **Total** | **~400** (well under the 20,000-file limit) |
