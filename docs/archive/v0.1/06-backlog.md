# Implementation backlog

Sized for a solo founder. **S** ≈ ≤1 day · **M** ≈ 2–4 days · **L** ≈ 1–2 weeks. Priorities: **P0** blocks MVP launch · **P1** MVP-desirable · **P2** post-MVP.
IDs are stable; reference them in commits (`DATA-03: …`).

Repository layout assumed (modular monolith):
```
/web        Next.js + TypeScript + Tailwind (pages, charts via ECharts, maps via MapLibre)
/api        FastAPI (read API = 05-openapi.yaml)
/engine     Python scoring engine (pure functions, no I/O) — imported by /api and /jobs
/jobs       Ingestion adapters + scheduled jobs (cron first, Airflow later)
/db         Migrations (start from 02-schema.sql), seeds
/content    Methodology + insight Markdown
```

---

## Epic 0 — Foundation (Months 1–2)

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| FND-01 | Pick brand name; check trademark/domain | S | P0 | Name decided; domain registered; recorded in PRD |
| FND-02 | Monorepo scaffold, lint/format, CI (GitHub Actions) | S | P0 | `web`, `api`, `engine`, `jobs` build & test in CI |
| FND-03 | Managed Postgres (dev + prod), object storage bucket | S | P0 | Connection via env vars; backups enabled |
| FND-04 | Migrations tool (Alembic) seeded from 02-schema.sql | S | P0 | `alembic upgrade head` creates schema on empty DB |
| FND-05 | Hosting for web + api; preview deploys | M | P0 | PR gets preview URL; main deploys to prod |
| FND-06 | 8–10 user interviews (students, journalists, analysts) | M | P0 | Notes in `/research`; top 5 jobs confirmed or revised |

## Epic 1 — Data foundation

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| DATA-01 | Seed `entities`: WB country list + region/income groups; ISO3, WB code, Wikidata QID | M | P0 | ~217 countries + groups; `member_of` relationships; slugs unique |
| DATA-02 | Seed `dimensions` and `topics` | S | P0 | 8 dimensions, 8 topics |
| DATA-03 | `sources` registry with licence review for WB WDI and UNDP HDR | S | P0 | `licence_reviewed_at` set; attribution text written |
| DATA-04 | Choose 30–50 launch indicators; write definitions, direction, bounds, applicability | M | P0 | Indicator YAML in `/db/seeds`; reviewed for per-capita vs absolute pairs |
| DATA-05 | Adapter framework: fetch → raw to object storage (sha256) → validate → upsert-as-supersede | L | P0 | Re-running the same release is a no-op; a revised value creates a new row and supersedes the old one |
| DATA-06 | World Bank Indicators API adapter | M | P0 | All DATA-04 WB indicators ingested 1990–latest; rejects logged |
| DATA-07 | UNDP HDR adapter (HDI components + official HDI) | M | P0 | Component indicators + official HDI values ingested for latest HDR |
| DATA-08 | Validation rules: unknown entity, unit mismatch, out-of-bounds, duplicate period | M | P0 | Each rule has a unit test; rejects land in `ingestion_rejects` |
| DATA-09 | Scheduled ingestion (weekly cron) + failure alert email | S | P1 | Job runs; failure emails founder |
| DATA-10 | Admin data-quality report (rejects, coverage, freshness by indicator) | M | P1 | Internal page behind auth |
| DATA-11 | Licence check for military indicators (e.g. SIPRI) before NCI includes them | S | P0 | Written decision in `/research/licences.md` |

## Epic 2 — Ranking engine

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| ENG-01 | Engine core types: IndexDefinition, inputs, results (pure Python, typed) | M | P0 | No DB imports in `/engine` |
| ENG-02 | Normalizations: min-max, goalposts, z-score, rank-percentile, log-min-max | M | P0 | Property tests: direction flip, bounds [0,1] for min-max |
| ENG-03 | Aggregations: weighted arithmetic, weighted geometric, pillar-of-pillars | M | P0 | Weights must sum to 1 (±1e-9) or raise |
| ENG-04 | Missing-data policies; coverage calc; exclusion reasons | M | P0 | No path produces a zero for a missing value (test) |
| ENG-05 | Ranking with ties ("=2") | S | P0 | Ties share rank; next rank skips |
| ENG-06 | Sensitivity runs (N perturbations, seeded RNG) → rank p05/p95 | M | P0 | Deterministic with fixed seed |
| ENG-07 | HDI official reproduction (UNDP goalposts, log income, geometric mean) | M | P0 | Golden test: matches UNDP published HDI within 0.001 for ≥ 95% of countries; diffs listed |
| ENG-08 | Publish job: select inputs → write `ranking_inputs` → compute → write results → hash → flip to published | M | P0 | Immutability triggers verified; re-run of published version reproduces byte-identical results |
| ENG-09 | Reproducibility CI: re-score last 3 published editions from stored inputs | S | P1 | CI fails on any diff |
| ENG-10 | Single-indicator ranking generator (definition from indicator slug) | S | P0 | 8–12 single-indicator rankings published |
| ENG-11 | NCI v1: indicator list, weights, written rationale, limitations | L | P0 | Methodology doc reviewed; sensitivity published; labelled ORIGINAL |

## Epic 3 — API

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| API-01 | FastAPI skeleton, problem+json errors, cursor pagination, OpenAPI served from 05-openapi.yaml | M | P0 | Contract test against spec (schemathesis) |
| API-02 | `/entities`, `/entities/{type}/{slug}`, `/entities/…/rankings` | M | P0 | 301 on renamed slug |
| API-03 | `/indicators`, `/indicators/{slug}` with coverage_by_year | S | P0 | |
| API-04 | `/observations` incl. `latest`, `as_of_release`, CSV | M | P0 | CSV includes attribution header row |
| API-05 | `/rankings`, `/rankings/{slug}`, `/results`, `/history`, `/methodology` | M | P0 | `movement` computed vs previous published edition |
| API-06 | `/compare` with `align_years` | M | P0 | 400 on mixed entity types |
| API-07 | `/search` (tsvector + trigram) with "X vs Y" intent | M | P0 | "inida vs chian" resolves to compare intent |
| API-08 | Licence gate on all export paths → 451 | S | P0 | Test with a source flagged non-redistributable |
| API-09 | Rate limiting + response caching (CDN headers per edition) | S | P1 | |
| API-10 | `/feedback/data-issues` | S | P1 | Creates row + emails founder |

## Epic 4 — Web (MVP)

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| WEB-01 | Design tokens, layout shell, nav, footer, light/dark | M | P0 | Matches wireframe nav |
| WEB-02 | Provenance chips component (SRC/CALC/EST/PROJ/AI) | S | P0 | Used by every value component |
| WEB-03 | Chart kit (ECharts): line, bar, sparkline, radar; "View as table" | M | P0 | Axe a11y check passes |
| WEB-04 | Choropleth map (MapLibre) with no-data grey + legend | M | P0 | |
| WEB-05 | Home page (wireframe 1) | M | P0 | |
| WEB-06 | Rankings index + ranking page (wireframe 2) incl. edition selector, filters, expand row | L | P0 | |
| WEB-07 | Ranking history & sensitivity pages | M | P1 | |
| WEB-08 | Country profile (wireframe 3) + dimension sub-pages | L | P0 | Absolute/per-capita toggle |
| WEB-09 | Region / income-group profile | S | P1 | |
| WEB-10 | Compare builder + canonical compare page (wireframe 4) | L | P0 | Canonical redirect; ⚠ on mismatched years |
| WEB-11 | Indicator catalogue + indicator page (wireframe 5) | M | P0 | |
| WEB-12 | Methodology page with KaTeX (wireframe 6) | M | P0 | |
| WEB-13 | Sources directory + source detail | S | P0 | |
| WEB-14 | Search box with instant results + intent redirect | M | P0 | |
| WEB-15 | Share images (OG) for rankings/compare/profiles | M | P1 | |
| WEB-16 | Topics hubs | S | P1 | |
| WEB-17 | Insights listing + article template | M | P0 | |
| WEB-18 | About, editorial policy, corrections, privacy, terms | S | P0 | |
| WEB-19 | "Report a data issue" modal | S | P1 | |

## Epic 5 — SEO, analytics, launch

| ID | Item | Size | Pri | Acceptance criteria |
|---|---|---|---|---|
| SEO-01 | sitemap.xml from DB; canonical tags; noindex rules | S | P0 | Per 03-sitemap.md rules |
| SEO-02 | Structured data: `Dataset` (indicator), `ItemList` (ranking), `Article` (insight) | S | P1 | Rich results test passes |
| SEO-03 | Core Web Vitals budget in CI (Lighthouse) | S | P1 | p75 LCP < 2.0s on ranking page |
| ANL-01 | Analytics events: search_submitted/result_clicked, compare_started/completed, download | S | P0 | Dashboard for PRD §9 metrics |
| CNT-01 | Write 3 launch insight articles | L | P0 | Each with evidence links, editor-reviewed |
| LCH-01 | Launch checklist: licence attribution audit, 404/500 pages, backups restore test | S | P0 | |

---

## Epic 6 — Intelligence layer (Months 5–6)

| ID | Item | Size | Pri |
|---|---|---|---|
| INT-01 | `POST /custom-indices/score` using engine | M | P1 |
| INT-02 | Index Builder UI (wireframe 7), assumptions checkbox, share link (noindex) | L | P1 |
| INT-03 | Accounts (email magic link) + saved views | M | P1 |
| INT-04 | Trend/anomaly batch job (YoY z-score, structural breaks) → candidate list | M | P1 |
| INT-05 | AI tool layer: `get_observations`, `run_ranking`, `compare_entities`, `get_methodology` wrappers over API | M | P1 |
| INT-06 | `/ask` endpoint: LLM + tools, citation enforcement (every figure must map to a tool result; otherwise strip and flag), store trace in `ai_answers` | L | P1 |
| INT-07 | `/ask` UI (wireframe 8) + "Ask about X" on profiles | M | P1 |
| INT-08 | AI eval set: 50 questions with expected figures; regression run in CI | M | P1 |
| INT-09 | Index Builder "Suggest from question" assistant | M | P2 |

## Epic 7+ — Later phases (titles only; refine at month 6 review)

- **M7-9**: Cities dataset + template · University dataset + template · Newsletter · Embeds (`/embed/...`) · Bulk edition downloads · Pro feature flagging.
- **M10-12**: Payments (Razorpay/Stripe) + pricing page · API keys + usage metering · API docs portal · Company/industry pilot dataset · Custom report pilot workflow.

---

## Suggested first 4 sprints (2 weeks each)

1. FND-01..05, DATA-01..03, ENG-01
2. DATA-04..08, ENG-02..05
3. ENG-06..08, ENG-10, API-01..05
4. ENG-07, API-06..08, WEB-01..06

Then sprints 5–8: remaining WEB/SEO/CNT items, ENG-11 (NCI) in parallel with content, launch at end of month 4.
