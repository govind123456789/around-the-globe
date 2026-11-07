# Implementation backlog (v0.2: free-forever, static-first)

Built from the *Build Plan* PDF (20 Oct 2026), with stable IDs and acceptance criteria added.
**Size:** S ≈ ≤1 day · M ≈ 2–4 days · L ≈ 1–2 weeks of part-time (12–15 h/week).
**🚀** = blocks the public launch.

## Phases and gates

The PDF's phase table is an image, and its text didn't come through. The dates below are my inference from the stated start (2 Nov 2026), the launch (~22 Feb 2027 = 16 weeks) and the tasks tagged to each phase. **Check them against the PDF.**

| Phase | Weeks / dates (inferred) | Ends with (gate) |
|---|---|---|
| **P0 Setup** | W1–2 · 2–15 Nov 2026 | "Hello world" page lists 5 WB indicators for all countries from R2; licences chosen; permission emails sent |
| **P1 Data** | W3–6 · 16 Nov–13 Dec | All launch adapters green in CI; licence gate live; weekly release to R2 |
| **P2 Product** | W7–12 · 14 Dec 2026–24 Jan 2027 | Rankings, profiles, compare, Index Builder, downloads usable on a preview URL; HDI check passes; reproducibility check passes |
| **P3 Launch + distribution** | W13–16 · 25 Jan–21 Feb (🚀 items), then months 5–6 | Public launch ~22 Feb 2027 after the launch checklist; then live AI, MCP and embeds |
| **P4 Expand + fund** | Months 5–12 and beyond | BYOK, archives/DOIs, universities, funder outreach |

If hours drop, stretch P2 rather than skip a gate. The launch date moves; the quality bar doesn't. First cut: 30 indicators and no map.

## Repo layout

```
pipeline/   adapters/, validate/, engine/, export/, tests/
site/       Astro (or Next.js static export)
worker/     Cloudflare Worker: AI proxy, MCP server, quotas
data/       licences.yaml, indicators.yaml, rankings/*.yaml
content/    methodology/, insights/, policies/
.github/    workflows: ci.yml, build-data.yml (cron), deploy.yml
```

---

## 1. Data pipeline (Python + DuckDB, GitHub Actions)

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| PIPE-01 🚀 | P0 | Repo skeleton: dirs above, Makefile, pre-commit, `ci.yml` | S | `make test` runs in CI on a public repo |
| PIPE-02 🚀 | P0 | Entity master: ~200 countries from Wikidata + ISO 3166 (QID, ISO3, names, region, income group) | M | `entities.parquet`; ISO3 unique; groups in `entity_groups` |
| PIPE-03 🚀 | P0 | `data/licences.yaml` for the 8 launch sources (start from [licences.example.yaml](licences.example.yaml)) | S | Each source has `licence_checked_on` set after reading the official page |
| PIPE-04 🚀 | P0 | WB adapter v0 for 5 indicators → Parquet → R2; "hello world" page | M | P0 gate |
| PIPE-05 🚀 | P1 | World Bank WDI adapter (API → raw JSON → Parquet) with per-series licence capture | M | Non-CC BY series are re-tiered automatically |
| PIPE-06 🚀 | P1 | UNDP HDR adapter | M | HDI components + official HDI values |
| PIPE-07 🚀 | P1 | OECD SDMX adapter | M | |
| PIPE-08 🚀 | P1 | TI CPI adapter (`no_modification: true`, `display_only`) | S | |
| PIPE-09 | P1 | GDELT adapter (media attention, monthly aggregates) | M | Citation + link rendered wherever shown |
| PIPE-10 🚀 | P1 | Validation: schema, units, year ranges, plausible bounds, outliers, coverage report per indicator | M | Each rule unit-tested; rejects in `validation_rejects`; build fails on unit change or missing years |
| PIPE-11 🚀 | P1 | Licence gate in CI: the four `gate_*` views in [02-schema.sql](02-schema.sql) must return 0 rows | S | Test fixtures prove each gate fails on a planted bad input |
| PIPE-12 🚀 | P1 | `build-data.yml` weekly cron → R2 `releases/YYYY-MM-DD/` + `latest` pointer + `manifest.json` | M | Raw files and checksums stored; job failure opens a GitHub issue |
| PIPE-13 🚀 | P2 | Ranking engine: min-max/goalposts/z-score, direction flip, log transform, weighted arithmetic & geometric means, pillars, coverage threshold, ties | L | Pure functions; property tests (direction flip, weights sum to 1, no zero-fill path) |
| PIPE-14 🚀 | P2 | Monte Carlo weight perturbation (seeded) → `rank_low` / `rank_high` | M | Deterministic for a fixed seed |
| PIPE-15 🚀 | P2 | HDI official-index check | M | Recomputed HDI matches UNDP published values to published precision; differences listed |
| PIPE-16 🚀 | P2 | Flagship composite v1 definition (economy, innovation, human capital), written rationale | L | Methodology v1 frozen; gates pass; sensitivity output exists |
| PIPE-17 🚀 | P2 | Single-indicator rankings generated from indicator catalogue | S | 8–12 rankings |
| PIPE-18 🚀 | P2 | Export: per-entity JSON, per-ranking-version JSON, per-indicator JSON, `matrix.json`, bulk CSV/Parquet + LICENSE + ATTRIBUTION | M | Matches 05-openapi.yaml schemas (JSON-schema test); every row has licence fields |
| PIPE-19 🚀 | P2 | Reproducibility check: rebuild the previous release from its raw files | S | Byte-identical `ranking_results` |
| PIPE-20 | P3 | Release-notes generator: what changed vs last edition | S | `/insights/releases/{date}` page |

## 2. Website (Astro or Next.js static export)

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| SITE-01 🚀 | P0 | Pick framework (Astro vs Next export), design tokens, light/dark, layout shell | M | Decision recorded in `docs/adr/0001-framework.md` |
| SITE-02 🚀 | P0 | Cloudflare deploy (Workers static assets) from `deploy.yml`; preview per PR | S | |
| SITE-03 🚀 | P1 | Provenance chip component (source · year · retrieved · licence · status) | S | Used for every displayed value |
| SITE-04 🚀 | P1 | Country profile template (key stats, sparklines, dimension scores, rankings, sources) | L | Renders from a single entity JSON |
| SITE-05 🚀 | P2 | Ranking page: sortable table, movement, filters, uncertainty bands, edition selector, methodology link | L | |
| SITE-06 | P2 | Choropleth map (MapLibre + Natural Earth TopoJSON); boundary choice documented | M | First thing cut if behind schedule |
| SITE-07 🚀 | P2 | Compare 2–5 countries; pre-rendered pages only for curated pairs; other combinations in the URL fragment, `noindex` | M | |
| SITE-08 🚀 | P2 | Methodology + sources pages with attribution rendered automatically | M | KaTeX formulas; change log |
| SITE-09 🚀 | P2 | Pagefind search | S | Finds countries, indicators, rankings |
| SITE-10 🚀 | P2 | Downloads page + API docs page rendered from 05-openapi.yaml | S | |
| SITE-11 🚀 | P2 | About pages: editorial policy, errata, licences/how to cite, funding, privacy | S | Policies published (see OPS-06) |
| SITE-12 | P3 | Embeddable chart iframe with attribution + backlink | M | |
| SITE-13 | P3 | SEO: sitemap, `Dataset` structured data, OG images generated at build | M | |
| SITE-14 | P3 | Lighthouse budget in CI | S | |
| SITE-15 | P3 | "Report a data issue" → prefilled GitHub issue / mailto | S | |

## 3. Index Builder (browser JavaScript)

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| IB-01 🚀 | P2 | Load + cache `matrix.json` | S | One fetch; works offline after first load |
| IB-02 🚀 | P2 | Pick indicators, set weights, choose normalisation/aggregation | M | Uses a JS port of the engine; **parity test**: JS and Python give identical ranks for the flagship definition |
| IB-03 🚀 | P2 | Live re-ranking, coverage warnings, state in the URL fragment | M | Pasting the URL reproduces the view |
| IB-04 | P3 | CSV export with inherited licence and source fields | S | |
| IB-05 | P3 | Three starter templates: study abroad, market entry, relocation | M | |

## 4. AI layer

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| AI-01 | P2 | Batch-generated summaries for every country and ranking page (batch API) | M | Number-check: every figure in the text matches the release JSON or the build fails |
| AI-02 | P3 | Typed read-only tools: `search_indicators`, `get_values`, `rank`, `compare` over release files | M | Shared by assistant and MCP |
| AI-03 | P3 | Worker proxy: Turnstile → intent cache (D1) → free-tier router → paid fallback | L | Model-agnostic config; EU/UK/CH traffic kept off training free tiers |
| AI-04 | P3 | Daily budget breaker ($3/day app-level) + provider cap on a separate billing account; per-IP quota; token and tool-call caps | M | Load test: breaker trips and UI shows the fallback state |
| AI-05 | P3 | Eval set of 200+ questions with expected numbers; CI gate at ≥95% | M | Blocks model or prompt changes below 95% |
| AI-06 | P3 | `/ask` UI incl. quota and breaker states (wireframe 8) | M | |
| AI-07 | P4 | Bring-your-own-key mode (key stays in the browser) | S | |

## 5. Open data API and MCP

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| API-01 🚀 | P2 | Static JSON API on R2 (`/v1/latest/...`, `/v1/releases/...`) documented | S | CORS open; cache headers immutable for dated releases |
| API-02 | P3 | Thin Worker MCP server (tools from AI-02) | M | Tested with at least one MCP client |
| API-03 | P4 | Mirror each release to Hugging Face Datasets; Zenodo DOI per annual release | S | |

## 6. Ops, legal and funding

| ID | Ph | Item | Size | Acceptance criteria |
|---|---|---|---|---|
| OPS-01 🚀 | P0 | Name clearance, domain, trademark filing | M | Name chosen; filing receipt |
| OPS-02 🚀 | P0 | Licences: CC BY 4.0 (data/indices), AGPL-3.0 core + MIT SDKs/embeds | S | `LICENSE` files in repo |
| OPS-03 🚀 | P0 | Permission emails to IMF, WHO, UNSD, SIPRI, Freedom House, RSF | S | Sent; tracked in `licences.yaml` notes |
| OPS-04 🚀 | P0 | Check employment terms on outside business activity | S | |
| OPS-05 | P1 | Cloudflare Web Analytics | S | |
| OPS-06 🚀 | P3 | Editorial independence, errata and conflict-of-interest policies | S | Published before launch (listed in launch checklist) |
| OPS-07 🚀 | P3 | Five outside reviewers test the preview; fix their issues | M | Launch checklist item |
| OPS-08 🚀 | P3 | Launch post + three data stories | M | |
| OPS-09 | P3 | Donation page; Digital Public Goods application | S | |
| OPS-10 | P4 | Funder outreach; decide on a Section 8 company with a co-director | — | Only once a named funder needs it |

### Accounts to create in week 1
GitHub organisation (public repos) · Cloudflare (domain, Workers, R2, D1, Web Analytics, Turnstile) · a separate billing account for each AI provider · Hugging Face organisation · project email on the domain.

## Week 1 checklist
1. Pick the name; check domain and trademark (OPS-01).
2. Create the GitHub org, Cloudflare account and R2 bucket.
3. Write `licences.yaml` for the eight launch sources (PIPE-03).
4. Build the country entity master and the WB adapter for five indicators (PIPE-02, PIPE-04).
5. Deploy a "hello world" page listing those five indicators for all countries from R2.
6. Send the six permission emails (OPS-03).

## Later (titles only)
- **M7–12:** Universities from OpenAlex + Leiden Open Edition + ROR (snapshots, not the metered API); GHSL city beta; separate V-Dem/OSM share-alike layers; eval set grown to 200–500.
- **M13–24:** Companies from EDGAR, GLEIF, Wikidata; annual DOI releases; JRC COIN-style methodology audit.
