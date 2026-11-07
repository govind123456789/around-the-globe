# Product Requirements Document — Free Global Rankings Platform

| | |
|---|---|
| **Name** | Around the Globe (chosen 2026-10-24; trademark and domain not yet checked). Domain in hand: zmetaboard.com |
| **Tagline** | Measure anything. Compare everything. Understand why. |
| **Status** | Draft v0.2, 2026-10-20. Replaces v0.1 (freemium, server-rendered), which is kept in [archive/v0.1](archive/v0.1/) |
| **Model** | Free forever for users. Open data under CC BY 4.0. Funded by the founder in year 1, then grants. No paid tiers |
| **Schedule** | Start 2 Nov 2026 · public launch about 22 Feb 2027 (16 weeks at 12–15 h/week) · AI, universities and funding in months 5–12 |

Companion documents: [02-schema.sql](02-schema.sql) · [licences.example.yaml](licences.example.yaml) · [03-sitemap.md](03-sitemap.md) · [04-wireframes.md](04-wireframes.md) · [05-openapi.yaml](05-openapi.yaml) · [06-backlog.md](06-backlog.md)

Inputs: the original strategy, *Bake the rankings, cap the AI, fund the founder* (research report) and *Free Global Rankings Platform — Build Plan* (20 Oct 2026). Costs and prices below come from those documents and are labelled as estimates there. I haven't re-verified them.

---

## 1. What changed from v0.1

| Area | v0.1 | v0.2 |
|---|---|---|
| Revenue | Free / Pro / Enterprise | Free only; donations, then grants; optional arm's-length services later |
| Serving | Next.js SSR + FastAPI + Postgres | Static site + static JSON/Parquet on Cloudflare R2; one small Worker |
| Database | Postgres is the system of record | DuckDB/Parquet built in GitHub Actions; Postgres optional, local only |
| Data sources | Any source, with a licence record | Green-tier only (allows commercial reuse and derivatives). CI fails the build on amber, red or share-alike leaks |
| Military / cost of living / peace / democracy | NCI included a military pillar | Deferred because the sources are red or share-alike. The flagship composite covers economy, innovation and human capital |
| Index Builder | Server scoring endpoint + accounts | Runs in the browser over the indicator matrix; state lives in the URL |
| AI | `/ask` as a headline feature | Batch-generated summaries first; live assistant behind Turnstile, a cache, quotas and a $3/day breaker |
| Accounts | Built in M5-6 | None at launch (no personal data held) |
| Own licences | Not specified | Data/indices CC BY 4.0; code AGPL-3.0 core + MIT SDKs/embeds; trademark on names |

## 2. Problem

People who want to know "how does country X compare with Y, and why?" have to stitch together several sites: one for raw statistics, one for a single ranking, another for explanations. Rankings they do find rarely show the formula, the data year, or how much data is missing. Many also forbid reuse, so a student, journalist or developer can't build on them.

## 3. Goals for v1 (launch, about week 16)

1. About 200 countries and 40–60 indicators, all from green-tier sources.
2. Every number shown or downloaded traces to a source, an observation year, a retrieval date, a status and a licence.
3. HDI reproduced with UNDP's methodology, matching published values to the published precision, and labelled official.
4. One flagship original composite (economy, innovation, human capital) with rank uncertainty bands and a sensitivity view, labelled as the platform's own index.
5. A browser Index Builder with shareable URLs and licence-carrying CSV export.
6. Bulk CSV/Parquet downloads under CC BY 4.0 with attribution files.
7. Any past release rebuilds byte-identically from stored raw files.
8. Running cost under ₹1,000/month until about 100k visitors/month (estimate).

### Non-goals for v1
- Live AI assistant (months 5–6). Precomputed AI summaries may ship at launch.
- Universities (months 7–12), cities (beta 7–12), companies (13–24).
- Military strength, cost of living, peace and democracy composites.
- User accounts, paid tiers, API keys.

## 4. Build principles

1. Precompute everything; the site serves static files only.
2. No number reaches a page or download unless its source licence permits it (enforced in CI).
3. The AI narrates; deterministic code computes.
4. Every published ranking is versioned and reproducible.
5. Each phase ends with something live, not a branch.

## 5. Users and primary jobs

| Persona | Job to be done | v1 must give them |
|---|---|---|
| **Curious public** | "Where does my country rank, and is that good?" | Clear ranking pages, maps, share images |
| **Student / educator** | "I need a citable figure." | Source, year and citation on every value; CSV download |
| **Journalist** | "I need a defensible comparison fast." | Compare page, methodology, embeds, edition date |
| **Analyst / developer** | "I want the method and the raw data." | Static JSON API, Parquet bulk files, CC BY licence |
| **Funders (indirect)** | "Is this used and trusted?" | Citations, downloads, DPG recognition, published policies |

## 6. The credibility contract

Every value is one of three kinds, and the UI labels it:

| Kind | Definition | UI treatment |
|---|---|---|
| **Observed** | Published by a source | Number + source chip + data year |
| **Calculated** | Produced by the ranking engine | Number + "Calculated" chip + methodology version |
| **Interpretation** | Narrative from an editor or AI | Separate block, author/AI label, citations inline |

Observation status: `measured`, `estimated`, `forecast`. No zero-fill and no imputation in v1.

## 7. Licensing requirements

### 7.1 Source tiers (enforced by `data/licences.yaml` + CI)

| Tier | Examples | Allowed |
|---|---|---|
| **Green — no conditions** | Wikidata (CC0), Natural Earth (PD), OpenAlex, Leiden Open Edition, ORCID | Everything |
| **Green — attribution** | World Bank WDI (CC BY 4.0, check each series), OECD (CC BY 4.0), UNDP HDR (CC BY 3.0 IGO), TI CPI (CC BY 4.0, **show raw, do not rescale**), GDELT, GHSL | Pages, composites, downloads, API; attribution and "modified" notices are added automatically |
| **Green — share-alike** | V-Dem (CC BY-SA 4.0), OpenStreetMap (ODbL) | Separate layers only; **never** feed the CC BY composite |
| **Amber** | IMF, WHO GHO, Freedom House, UNdata, RSF | Not ingested until written permission arrives |
| **Red** | UN Comtrade, SIPRI (bulk), QS, THE, Numbeo, Global Firepower, Statista | Link out / cite single facts in editorial text only |
| **Unverified** | ILOSTAT, UN DESA WPP, UN-Habitat, GODL-India | Treat as amber until the official licence text is read |

- **LIC-1** Each indicator maps to exactly one source; each source has a tier and the flags `commercial_ok`, `derivatives_ok`, `share_alike`, `no_modification`.
- **LIC-2** The build fails if a published file contains an indicator from an amber, red or unverified source.
- **LIC-3** The build fails if a share-alike or `no_modification` indicator is an input to a CC BY composite.
- **LIC-4** World Bank ingestion reads each series' own licence field; a non-CC BY series gets its own tier and isn't treated as World Bank default.
- **LIC-5** Every exported row and file has `source`, `source_licence`, `source_url`, `retrieved_at`, `modified`.

### 7.2 Platform's own output
- Data and indices: **CC BY 4.0**. Code: **AGPL-3.0** core; **MIT** SDKs, MCP client and chart embeds.
- Index Builder exports state that user-made indices inherit their sources' licences.
- Register a trademark on the platform name and flagship index name.

## 8. Functional requirements — v1

### 8.1 Pipeline
- **FR-D1** Source adapters for World Bank WDI, UNDP HDR, OECD SDMX, TI CPI, GDELT, Wikidata (entities) and Natural Earth (boundaries).
- **FR-D2** Each run stores raw downloads with a checksum in a dated release folder and writes a `source_releases` row.
- **FR-D3** Validation: schema, units, year ranges, plausible-value bounds, outliers. Failures stop the build and are listed in the release notes.
- **FR-D4** Revisions don't overwrite: each release is a complete snapshot, so old editions rebuild from their own raw files.
- **FR-D5** Schedule: weekly cron in GitHub Actions (public repo, so minutes are free). Outputs go to R2 under `/releases/YYYY-MM-DD/` with a `latest` pointer.

### 8.2 Ranking engine (Python, deterministic)
- **FR-R1** Normalisation: min-max (optional goalposts), z-score; direction flip; optional log transform.
- **FR-R2** Aggregation: weighted arithmetic and weighted geometric means; two-level pillars.
- **FR-R3** Coverage rule: rank an entity only if it has data for at least a set share (default 70%) of the composite's weight. Weights are renormalised over available data; there is no zero-fill.
- **FR-R4** Monte Carlo weight perturbation (seeded) gives `rank_low` / `rank_high` for each entity.
- **FR-R5** Ties shown as "=12".
- **FR-R6** HDI reproduction check against UNDP published values.
- **FR-R7** Release notes generator: what changed compared with the last edition.

### 8.3 Exports
- **FR-X1** Per-entity JSON, per-ranking JSON (one per version), per-indicator JSON.
- **FR-X2** A compact entity × indicator matrix (a few MB) for the Index Builder.
- **FR-X3** Bulk CSV + Parquet with `LICENSE.txt` and `ATTRIBUTION.md`.
- **FR-X4** These files *are* the public API (see 05-openapi.yaml). Documented with stable paths.

### 8.4 Website (Astro or Next.js static export)
- **FR-W1** Country profile: key stats, sparklines, dimension scores, rankings it appears in, sources.
- **FR-W2** Ranking page: sortable table, rank movement, filters, uncertainty bands, methodology link, edition selector.
- **FR-W3** Choropleth map (MapLibre + Natural Earth TopoJSON; boundary dataset chosen deliberately because India regulates map depiction).
- **FR-W4** Compare 2–5 countries. Pre-rendered canonical URLs only for popular pairs; other combinations render on the client from JSON and are `noindex`.
- **FR-W5** Methodology and sources pages with attribution rendered automatically.
- **FR-W6** Search with Pagefind (no server).
- **FR-W7** Every value shows source, data year and retrieval date.

### 8.5 Index Builder (browser)
- **FR-B1** Loads the indicator matrix once (cached).
- **FR-B2** Pick indicators (green, CC BY-compatible only), set weights, choose normalisation and aggregation.
- **FR-B3** Live re-ranking with coverage warnings; the whole state is encoded in the URL.
- **FR-B4** CSV export carries inherited licence and source fields.
- **FR-B5** (P3) Three starter templates: study abroad, market entry, relocation.

### 8.6 Analytics & feedback
- **FR-F1** Cloudflare Web Analytics (cookieless).
- **FR-F2** "Report a data issue" links to a prefilled GitHub issue or email (no server-side form).

## 9. AI requirements

### 9.1 Static AI (P2)
- Batch-generated summaries for every country and ranking page, once per data refresh, through batch APIs (about 50% off).
- Summaries are grounded only in pipeline numbers. A check compares every figure in the text with the source JSON and fails the build on a mismatch.
- Labelled AI-generated, with a link to the numbers they cite.

### 9.2 Live assistant (P3, months 5–6)
Request path: **Turnstile → intent cache (D1) → free-tier router (Workers AI, Groq) → cheapest paid model that passes evals**.
- Typed read-only tools only: `search_indicators`, `get_values`, `rank`, `compare`. No text-to-SQL. Every number comes from tool output.
- Caps: per-IP daily quota, tool-iteration cap, token ceiling.
- **Budget breaker**: an app-level spend counter switches the assistant off at $3/day and shows precomputed answers, plus a provider spend cap on a **separate billing account**.
- EU/UK/CH traffic is not routed to any provider's free tier that trains on content.
- Eval set of 200+ questions with expected numbers. A model or prompt change ships only at 95%+ correct.
- (P4) Bring-your-own-key, with the key stored only in the browser.

### 9.3 MCP server (P3)
A thin Worker MCP server exposing the same read-only tools, so AI assistants can query and cite the platform.

## 10. Non-functional requirements

| Area | Requirement |
|---|---|
| Cost | < ₹1,000/month to ~100k visitors; worst-case AI ≈ $90/month under the breaker (estimates) |
| Hosting limits | Free Workers plan holds 20,000 static files; move to Workers Paid ($5) only past that or past 100k Worker requests/day |
| Performance | Pages read small precomputed JSON; DuckDB-WASM loaded only in the data explorer; Lighthouse budget in CI |
| Reproducibility | Rebuilding a past release from stored raw files gives byte-identical ranking results (CI) |
| Accessibility | WCAG 2.2 AA; every chart has a table alternative |
| Privacy | No accounts, no cookies for analytics; nothing personal stored |
| Archive | Releases mirrored to Hugging Face Datasets; Zenodo DOIs (P4) |

## 11. Launch indicator set (target 40–60)

| Dimension | Example indicators | Source (licence) |
|---|---|---|
| Economy | GDP per capita PPP, GDP growth, inflation, unemployment, exports % GDP | World Bank WDI (CC BY 4.0) |
| Human development | HDI, life expectancy, expected years of schooling, GNI per capita | UNDP HDR (CC BY 3.0 IGO) |
| Innovation & tech | R&D % GDP, researchers per million, internet users, high-tech exports | WDI; OECD (CC BY 4.0) |
| Health | Infant mortality, health spending per capita, physicians per 1,000 | WDI |
| Governance | Corruption Perceptions Index (raw, not rescaled; display only) | TI (CC BY 4.0) |
| Environment & energy | CO₂ per capita, renewable share, electricity access | WDI |
| Demography | Population, median age, urban share | WDI |
| Media attention | News-mention volume and tone | GDELT (citation + link) |
| Identity & maps | Names, codes, capitals, boundaries | Wikidata (CC0), Natural Earth (PD) |

Because of TI's "not changed" request, CPI stays out of the flagship composite unless the engine can use it unmodified.

## 12. Launch checklist

- Methodology v1 frozen and published, with change log.
- Every page shows source, data year and retrieval date.
- Composite labelled as the platform's own; official indices labelled official.
- Sensitivity view live.
- Errata page and contact address live; editorial independence and conflict-of-interest policies published.
- Downloads include licence and attribution files.
- Five outside reviewers (journalist, economist, student, data engineer, policy analyst) have tried it and their issues are fixed.
- Launch post and three data stories ready.

## 13. Metrics (set targets after 4 weeks of baseline)

Monthly visitors and returning share · Compare and Index Builder sessions per 100 visits · downloads, API hits, embeds · citations by media, researchers and Wikipedia · data freshness lag per source · AI cost per day and cache hit rate.

## 14. Funding and legal track (runs alongside the build)

| When | Action |
|---|---|
| P0 | Name clearance, domain, trademark filing; choose licences; email IMF, WHO, UNSD, SIPRI, Freedom House and RSF asking for free-site permission; check employment terms on outside activity |
| P3 | Donation page; publish editorial, errata and COI policies; submit Digital Public Goods application |
| P4 (months 5–12) | Funder outreach (open-knowledge funders, Indian philanthropy, a university partner); form a Section 8 company with a co-director only once a named funder needs it; FCRA prior permission per foreign grant |
| Ongoing | Keep any single funder below 60% of income; publish a firewall/disclosure policy before any paid service |

Startup credits (Cloudflare, AWS Activate, Google, Microsoft) need a registered company; apply once one is attached, and check eligibility honestly.

## 15. Risks

| Risk | Mitigation |
|---|---|
| Part-time hours shrink | Cut to 30 indicators and drop the map before cutting quality gates; the date moves, the bar doesn't |
| Permissions refused or ignored | Launch on green sources; add layers as permissions arrive |
| Free tiers change or end | Static-first design; model-agnostic AI router; spend caps |
| Ranking seen as biased | Published methodology, sensitivity view, errata, editorial policy |
| Licence leak | CI licence gate; licence fields on every row |
| Employer conflict-of-interest rules | Check terms before launch |
| No grant in year 1 | Costs are small; founder funds hosting longer |

## 16. Open questions

1. Final brand name (blocks trademark, domain, share-image template).
2. Astro or Next.js static export (backlog SITE-01).
3. Flagship composite: exact indicators and weights, with a written rationale.
4. Whether to use CPI in the composite given TI's "not changed" request.
5. Which boundary dataset to use for India-facing maps.
6. The PDF's phase/gate table didn't come through as text. The phase dates in 06-backlog.md are my inference and need checking against it.
