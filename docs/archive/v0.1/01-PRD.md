# Product Requirements Document — Global Rankings & Intelligence Platform

| | |
|---|---|
| **Working name** | TBD (candidates: Atlas Intelligence, WorldMetrics, GlobalRank) — domain in hand: zmetaboard.com |
| **Tagline** | Measure anything. Compare everything. Understand why. |
| **Status** | Draft v0.1 — 2026-10-20 |
| **Scope of this PRD** | Public MVP (roadmap months 1–4) in full detail; Intelligence layer (months 5–6) at requirement level; later phases as constraints on today's design |

Companion documents: [02-schema.sql](02-schema.sql) · [03-sitemap.md](03-sitemap.md) · [04-wireframes.md](04-wireframes.md) · [05-openapi.yaml](05-openapi.yaml) · [06-backlog.md](06-backlog.md)

---

## 1. Problem

People who want to know "how does country X compare with Y, and why?" have to stitch together several sites: one for raw statistics, one for a single ranking, another for explanations. Rankings they do find rarely show the formula, the data year, or how much data is missing, so they can't judge whether to trust them.

## 2. Goals for the MVP

1. A user can find any country and any of the first 30–50 indicators in under 10 seconds from the homepage.
2. Every number shown traces to a source, an observation year, and a status (measured / estimated / forecast / modelled).
3. At least one official index (HDI) is reproduced using its official methodology and labelled as official.
4. At least one original composite index (National Capability Index, NCI) is published with methodology, coverage, and a sensitivity check.
5. Any published ranking can be reconstructed exactly from stored versions (reproducibility = 100% for published editions).

### Non-goals for the MVP
- Cities, universities, companies, industries (the data model supports them; no data or pages yet).
- User accounts, saved views, paid tiers, API keys (designed, not built).
- AI research assistant (month 5–6).
- Custom Index Builder UI (month 5–6; the scoring engine it needs *is* in MVP).

## 3. Users and primary jobs (launch audiences)

| Persona | Job to be done | MVP must give them |
|---|---|---|
| **Curious public** | "Where does my country rank, and is that good?" | Clean ranking pages, maps, share images |
| **Student / educator** | "I need a citable figure for an assignment." | Source, year and citation text on every value; CSV download |
| **Journalist** | "I need a defensible comparison quickly." | Compare page, methodology page, chart embed, edition date |
| **Independent analyst** | "I want to check the method and the raw data." | Indicator time series, coverage, weights, downloadable edition |

Business, investor, policy and developer audiences are deferred; their needs constrain the design (API-first, versioned data) but don't add MVP scope.

## 4. Output types — the credibility contract

Every value rendered in the product is one of three kinds and the UI labels it:

| Kind | Definition | UI treatment |
|---|---|---|
| **Observed** | A value published by a source | Plain number + source chip + year |
| **Calculated** | Produced by a ranking engine formula | Number + "Calculated" chip + link to methodology version |
| **Interpretation** | Narrative written by an editor or AI | Visually separate block, author/AI label, citations inline |

Observation status (orthogonal to kind): `measured`, `estimated`, `projected`, `modelled`, `imputed`. Imputed values are never used in an official index and are flagged everywhere.

## 5. Functional requirements — MVP

### 5.1 Data foundation
- **FR-D1** Ingest country indicators from the World Bank Indicators API and the UNDP HDR datasets via source adapters (one adapter per source).
- **FR-D2** Every ingestion run creates a `source_release` record; observations reference the release they came from.
- **FR-D3** Revisions never overwrite: a revised value creates a new observation row; the prior row is marked superseded.
- **FR-D4** Schema checks reject rows with unknown entity codes, wrong units, or values outside indicator-declared bounds; rejects are logged and visible in an admin report.
- **FR-D5** Entity identity resolved via ISO 3166-1 alpha-3, with Wikidata QID and World Bank code stored as cross-references.
- **FR-D6** Each source has a licence record (licence, attribution text, commercial-use flag, redistribution flag). Download and export endpoints refuse to include data whose licence forbids redistribution.

### 5.2 Ranking engine
- **FR-R1** A ranking is a definition (entity type, eligibility rules, indicators, weights, direction, normalization, aggregation, missing-data policy). A *version* of a ranking is immutable once published.
- **FR-R2** Supported normalizations: min-max (with optional fixed goalposts), z-score, rank-percentile, log then min-max.
- **FR-R3** Supported aggregations: weighted arithmetic mean, weighted geometric mean (needed for HDI), and pillar-of-pillars (two-level).
- **FR-R4** Missing-data policy is per ranking: `exclude_entity` (below a coverage threshold), `reweight_available`, or `fail`. Never zero-fill.
- **FR-R5** Each result row stores score, rank (with ties as "=12"), coverage %, number of indicators used, and calculation version.
- **FR-R6** Sensitivity: on publish, the engine runs N (default 1,000) weight perturbations (±25% per pillar, renormalized) and stores each entity's rank interval (5th–95th percentile). Displayed as a rank range.
- **FR-R7** Engine is a deterministic Python service; same inputs + version ⇒ byte-identical outputs (tested in CI).

### 5.3 Rankings pages
- **FR-P1** Table: rank, movement vs previous edition, entity, score, coverage, rank range; sortable by any pillar/indicator.
- **FR-P2** Choropleth map toggle.
- **FR-P3** Filters: region, income group, population band, minimum coverage.
- **FR-P4** Edition selector (past published editions).
- **FR-P5** Methodology panel and link to full methodology page.
- **FR-P6** Download CSV of the current edition (licence-permitting); share image; embed code.

### 5.4 Entity (country) profiles
- **FR-E1** Header: name, flag, region, income group, population, data freshness summary.
- **FR-E2** "Where it ranks": every ranking the entity appears in, with rank and movement.
- **FR-E3** Indicator panels grouped by dimension, each with a sparkline, latest value, year, source, and peer percentile.
- **FR-E4** Separate absolute vs per-capita views where an indicator has both.
- **FR-E5** Related entities (region peers; later: capital, cities, universities).

### 5.5 Compare
- **FR-C1** Compare 2–5 entities of the same type.
- **FR-C2** Side-by-side indicator table with the latest *common* year highlighted where years differ.
- **FR-C3** Radar/pillar chart for any ranking all entities appear in.
- **FR-C4** Canonical URLs for pairs (`/compare/india-vs-china`), alphabetically canonicalised with redirect.

### 5.6 Search
- **FR-S1** Single search box over entities, indicators, rankings, topics; PostgreSQL full-text + trigram for typos.
- **FR-S2** Query patterns recognised: "X vs Y" → compare; "<indicator> <country>" → profile panel.

### 5.7 Data explorer (MVP-lite)
- **FR-X1** Indicator page: definition, unit, direction, source, coverage by year, world map, full time-series chart.
- **FR-X2** Download indicator CSV (licence-permitting).

### 5.8 Methodology & sources
- **FR-M1** One methodology page per ranking version: formula (rendered math), indicator list with weights, transformations, eligibility, missing-data policy, limitations, change log.
- **FR-M2** Sources directory with licence and attribution for each source.

### 5.9 Feedback & analytics
- **FR-F1** "Report a data issue" on every value (creates a ticket with entity, indicator, observation id).
- **FR-F2** Privacy-respecting analytics (page views, search success, compare completion).

## 6. Requirements — Intelligence layer (months 5–6)

- **Index Builder v1**: choose entity set, pick indicators from the catalogue (only those applicable to the entity type), set weights/direction, preview result + sensitivity, save privately; publish requires the user to tick an assumptions review.
- **Trend & anomaly detection**: statistical tests (structural break, z-score of YoY change vs history) run in batch; only flagged items go to narrative generation.
- **AI explanations**: the LLM calls tools (`get_observations`, `run_ranking`, `compare_entities`, `get_methodology`) against the API; it never produces a number that didn't come from a tool result. Every sentence containing a figure carries a citation to observation/ranking ids. Answers that cannot be grounded say so.
- **Reports**: editor-reviewed analysis articles linked to the rankings and entities they cite.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Ranking and profile pages server-rendered; p75 LCP < 2.0 s on 4G; API p95 < 300 ms for cached reads |
| Availability | 99.5% monthly for public pages (MVP) |
| Reproducibility | Published edition = immutable inputs + methodology version + engine version; CI re-runs last 3 editions |
| Accessibility | WCAG 2.2 AA; every chart has a table alternative |
| SEO | Stable canonical URLs, structured data (`Dataset`, `ItemList`), sitemap.xml, no thin auto-generated prose |
| Licensing | Export/embeds blocked automatically for non-redistributable sources |
| Security | Admin behind SSO; public API read-only; rate limiting on all endpoints |
| i18n | English at launch; strings externalised; numbers locale-formatted (Indian grouping available) |

## 8. Launch content (MVP)

- **Entities**: ~217 countries/territories (World Bank list), plus region and income-group aggregates as entities of type `country_group`.
- **Indicators**: 30–50 across Economy, Human development, Demography, Health, Education, Technology, Energy & environment, Governance. Initial list is backlog item DATA-04.
- **Rankings**: HDI (official reproduction), NCI v1 (original, clearly labelled), plus 8–12 single-indicator rankings (GDP, GDP per capita PPP, life expectancy, etc.).
- **Content**: 3 original analysis pieces at launch.

## 9. Success metrics (baseline first, then targets)

Search-to-result success, comparison completion rate, 30-day return rate, source coverage per ranking, data freshness vs source schedule, reproducibility rate (target: 100%), issue reports resolved within 14 days.

## 10. Risks specific to the MVP

| Risk | Mitigation in this PRD |
|---|---|
| NCI accused of bias (military pillar) | Rank ranges, sensitivity panel, explicit limitations section, no "strongest country" headline copy |
| World Bank data gaps for small states | Coverage threshold + visible "insufficient data" state, not zero |
| HDI reproduction drifts from UNDP | Golden-file test vs UNDP published scores (tolerance 0.001) |
| Solo-founder bandwidth | Modular monolith; one Postgres; scheduled jobs; defer accounts and payments |

## 11. Open questions

1. Final brand name (blocks domain, logo, share-image template).
2. NCI v1 indicator list and weights — needs a written rationale before publish.
3. Whether military indicators (e.g. SIPRI expenditure) have licence terms compatible with republication — check before including.
4. Analytics provider (self-hosted Plausible/Umami vs managed).
5. Hosting provider for Next.js + FastAPI + Postgres.
