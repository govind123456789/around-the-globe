# Implementation backlog (v0.3: status against the current build)

Built from the *Build Plan* PDF (20 Oct 2026), with stable IDs and acceptance criteria added. Statuses below were
set on 2026-11-27 by reading the repository (code, tests, workflows, data files). The tests were not run for this
update, and anything outside the repo (accounts, emails sent, secrets) is marked "not in repo".

**Size:** S ≈ ≤1 day · M ≈ 2–4 days · L ≈ 1–2 weeks of part-time (12–15 h/week).
**🚀** = blocks the public launch.
**Status:** ✅ done · 🟡 partly done · 🔁 done differently from the plan · ⬜ not started · ❓ not in repo (check by hand)

## What changed from the original plan

| Plan | Current build |
|---|---|
| Astro or Next.js static export | Python + Jinja static build (`pipeline/build_site.py`, `site/templates/`), client JS in `site/static/js/` |
| Cloudflare R2 for releases | `dist/` served as Workers static assets; each release archived as a GitHub Release (`data-<date>`), with `/v1/releases/<date>/…` redirected there |
| Pagefind search | Own search and command palette in `app.js` |
| `build-data.yml` + `deploy.yml` | One workflow, `build-and-deploy.yml` (weekly, strict licence gate), plus `ci.yml`, `quality.yml` and `fetch-india.yml` |
| Worker = AI proxy and MCP | Worker is an API-key and rate-limit layer in front of `/v1/*` (`worker/`); no AI or MCP code yet |
| Repo layout `pipeline/adapters/, validate/, export/` | Flat modules: `fetch.py`, `build_data.py`, `engine.py`, `build_site.py` and feature modules |

## Phases and gates

Dates are inferred from the stated start (2 Nov 2026) and a launch of about 22 Feb 2027 (the PDF's phase table did not come through as text).

| Phase | Weeks / dates (inferred) | Ends with (gate) | State |
|---|---|---|---|
| **P0 Setup** | W1–2 · 2–15 Nov 2026 | Data page for 5 WB indicators; licences chosen; permission emails sent | Built; emails ❓ |
| **P1 Data** | W3–6 · 16 Nov–13 Dec | Adapters green in CI; licence gate live; weekly release | Built (weekly workflow needs Cloudflare secrets ❓) |
| **P2 Product** | W7–12 · 14 Dec 2026–24 Jan 2027 | Rankings, profiles, compare, Index Builder, downloads; HDI check; reproducibility check | Built except the reproducibility check |
| **P3 Launch + distribution** | W13–16 · 25 Jan–21 Feb | Public launch after the launch checklist; then AI, MCP, embeds | Launch checklist open; AI/MCP not started |
| **P4 Expand + fund** | Months 5–12 | BYOK, archives/DOIs, universities, funders | Universities and cities already built; rest open |

The build is well ahead of the dates. What remains is mostly launch work outside the code.

## 1. Data pipeline (Python + DuckDB, GitHub Actions)

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| PIPE-01 🚀 | P0 | Repo skeleton, CI | ✅ | `ci.yml` runs `pytest`. No Makefile or pre-commit file in the repo |
| PIPE-02 🚀 | P0 | Entity master | 🟡 | Country names in `data/country_names.yaml`, FIPS→ISO via Wikidata; no `entities.parquet` as specced |
| PIPE-03 🚀 | P0 | `data/licences.yaml` | ✅ | Every source has `licence_checked_on` (21 Oct–17 Nov 2026) |
| PIPE-04 🚀 | P0 | WB adapter v0 | ✅ | Superseded by the full WDI adapter |
| PIPE-05 🚀 | P1 | World Bank WDI adapter | ✅ | Per-series licence checked on every fetch; WGI too |
| PIPE-06 🚀 | P1 | UNDP HDR adapter | ✅ | HDI, IHDI, GDI, GII, PHDI and components |
| PIPE-07 🚀 | P1 | OECD adapter | ✅ | Tax revenue, average wages (from CSV, not SDMX) |
| PIPE-08 🚀 | P1 | TI CPI adapter | ✅ | Display only, via Our World in Data |
| PIPE-09 | P1 | GDELT adapter | ✅ | GDELT 1.0 daily files; news volume and tone |
| PIPE-10 🚀 | P1 | Validation | 🟡 | Validation and reject handling are in `build_data.py`; per-indicator coverage report not confirmed |
| PIPE-11 🚀 | P1 | Licence gate in CI | ✅ | `test_licence_gate.py`; `--strict` fails on unset `licence_checked_on` |
| PIPE-12 🚀 | P1 | Weekly release job | 🔁 | `build-and-deploy.yml`, Mondays 03:00 UTC; GitHub Release instead of R2; issue-on-failure not confirmed |
| PIPE-13 🚀 | P2 | Ranking engine | ✅ | `engine.py`, tests in `test_engine.py` |
| PIPE-14 🚀 | P2 | Monte Carlo weight perturbation | ✅ | `engine.sensitivity`; ±25% over 200 seeded runs; also in `engine.js` |
| PIPE-15 🚀 | P2 | HDI official-index check | ✅ | `test_hdi_matches_undp_published_values` |
| PIPE-16 🚀 | P2 | Flagship composite v1 | ✅ | Capability, HDI, health system, digital readiness and green transition indices, each with a methodology page |
| PIPE-17 🚀 | P2 | Single-indicator rankings | ✅ | 52 rankings at the 2026-11-10 release |
| PIPE-18 🚀 | P2 | Export (JSON, CSV, Parquet) | ✅ | Static JSON API under `dist/v1/`; bulk tables via DuckDB. JSON-schema test against `05-openapi.yaml` not found |
| PIPE-19 🚀 | P2 | Reproducibility check | ⬜ | No test found that rebuilds the previous release byte-for-byte. `test_release.py` checks the built release only |
| PIPE-20 | P3 | Release notes | ✅ | `changes.py` classifies rank moves (method, revision, new year, others); `release_notes.html` |

## 2. Website

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| SITE-01 🚀 | P0 | Framework and layout shell | 🔁 | Jinja, not Astro. `docs/adr/0001-framework.md` was never written |
| SITE-02 🚀 | P0 | Cloudflare deploy | ✅ | `wrangler.jsonc`, deploy step in the weekly workflow. Preview per PR not found |
| SITE-03 🚀 | P1 | Provenance chip | ✅ | `prov.js`; trust levels from `trust.py` |
| SITE-04 🚀 | P1 | Country profile | ✅ | Plus generated summaries, question tabs and a history page per country |
| SITE-05 🚀 | P2 | Ranking page | ✅ | Plus "why this rank" explanations (`explain.py`) |
| SITE-06 | P2 | Choropleth map | ✅ | Natural Earth India point-of-view boundaries, MapLibre self-hosted |
| SITE-07 🚀 | P2 | Compare 2–5 countries | ✅ | 20 curated pairs in `data/site.yaml`; about 500 pair pages |
| SITE-08 🚀 | P2 | Methodology and sources pages | ✅ | Plus "sources compared" (`reconcile.py`) and live-estimates method page |
| SITE-09 🚀 | P2 | Search | 🔁 | Own search and command palette, not Pagefind |
| SITE-10 🚀 | P2 | Downloads and API docs | ✅ | `downloads.html`, `api.html` |
| SITE-11 🚀 | P2 | About pages and policies | ✅ | About, editorial policy, errata, licences, funding, privacy in `content/pages/` |
| SITE-12 | P3 | Embeddable chart | ✅ | `/embed/rankings/<id>/` and the Embed button |
| SITE-13 | P3 | SEO, sitemap, OG images | 🟡 | Sitemap and `og.py` share cards done; `Dataset` structured data not confirmed |
| SITE-14 | P3 | Lighthouse budget in CI | ✅ | `quality.yml` plus `lighthouserc.json`; axe check fails on serious or critical |
| SITE-15 | P3 | Report a data issue | ✅ | Site-wide footer link |

## 3. Index Builder

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| IB-01 🚀 | P2 | Load and cache `matrix.json` | ✅ | `builder.js` |
| IB-02 🚀 | P2 | Indicators, weights, normalisation, aggregation | ✅ | `engine.js` port; `test_parity.py` |
| IB-03 🚀 | P2 | Live re-ranking, state in URL | ✅ | Rank ranges appear after the sliders stop |
| IB-04 | P3 | CSV export with licence and source fields | ❓ | Not confirmed in `builder.js` |
| IB-05 | P3 | Starter templates | ❓ | Not confirmed |

## 4. AI layer

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| AI-01 | P2 | Summaries for country and ranking pages | 🔁 | Built without an LLM: `summaries.py` writes every sentence from the data, so the number-check is true by construction. No batch-API summaries |
| AI-02 | P3 | Typed read-only tools | ⬜ | |
| AI-03 | P3 | Worker proxy: Turnstile, cache, router | ⬜ | `worker/` has API keys and rate limits only |
| AI-04 | P3 | Budget breaker and quotas | ⬜ | Per-minute rate limits exist for the API, not for AI |
| AI-05 | P3 | Eval set, CI gate at ≥95% | ⬜ | |
| AI-06 | P3 | `/ask` UI | 🟡 | Page exists as a placeholder ("Coming months 5–6") |
| AI-07 | P4 | Bring-your-own-key | ⬜ | |

## 5. Open data API and MCP

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| API-01 🚀 | P2 | Static JSON API | ✅ | `dist/v1/`; dated links redirect to GitHub Releases. Worker adds optional free API keys (600 requests a minute) over the anonymous 60, hashed keys in D1 |
| API-02 | P3 | MCP server | ⬜ | |
| API-03 | P4 | Hugging Face mirror and Zenodo DOI | ⬜ | |

## 6. Ops, legal and funding

| ID | Ph | Item | Status | Notes |
|---|---|---|---|---|
| OPS-01 🚀 | P0 | Name, domain, trademark | 🟡 | Name chosen 2026-10-24. Trademark and domain unchecked; site runs on a `workers.dev` address |
| OPS-02 🚀 | P0 | Licences | ✅ | `LICENSE` (AGPL-3.0), `LICENSE-DATA.md`. Data licence is CC BY 4.0 |
| OPS-03 🚀 | P0 | Permission emails | ❓ | IMF, WHO and SIPRI are recorded as excluded until permission. No entries for Freedom House, RSF or UNSD |
| OPS-04 🚀 | P0 | Employment terms check | ❓ | |
| OPS-05 | P1 | Cloudflare Web Analytics | 🟡 | Code is in; off until `cloudflare_analytics_token` is set in `data/site.yaml` |
| OPS-06 🚀 | P3 | Editorial, errata and COI policies | ✅ | Published as pages |
| OPS-07 🚀 | P3 | Five outside reviewers | ⬜ | |
| OPS-08 🚀 | P3 | Launch post and three data stories | 🟡 | Stories set to `published` 2026-11-27; launch posts drafted in `docs/launch/launch-drafts.md`, not posted |
| OPS-09 | P3 | Donation page; DPG application | ❓ | `funding.md` page exists; no donation page or DPG application found |
| OPS-10 | P4 | Funder outreach | ⬜ | |

## Built beyond the original plan

- **Geopolitics:** hub, blocs, conflicts (UCDP), UN voting, displacement (UNHCR), sanctions, defence profiles, risk score, watchlist, news (GDELT).
- **History:** country history pages from Cliopatria, Wikidata, UCDP and Maddison, with a consistency check.
- **The Lab:** clustered correlation matrix, income-adjusted findings, partial correlations, time twins, years to target.
- **Cities and universities:** GHSL urban centres and the 2,000 most-cited OpenAlex universities.
- **India states:** state-level tables from data.gov.in (`india.py`, `fetch-india.yml`).
- **Markets, reports and the report builder, quiz, interface translations (`i18n`), a globe, live estimates.**
- **Trust levels** on every value, **sources compared** (World Bank vs UN), and **why-it-moved** classification of rank changes.
- **V-Dem** democracy indices, share-alike, shown separately from the CC BY composites.

## Next steps, in order

1. Check the trademark and register a domain; then set `base_url` in `data/site.yaml`. 🚀
2. Add the Cloudflare secrets and run the first deploy. 🚀
3. Send the outstanding permission emails (OPS-03) and record the dates in `licences.yaml`. 🚀
4. Arrange the five outside reviewers; fix what they find. 🚀
5. Add the reproducibility check (PIPE-19). 🚀
6. Post the launch drafts after re-checking their numbers against the live pages.
7. Switch on analytics (token); then start AI-02 onwards.

## Later (titles only)

- **M7–12:** separate OSM share-alike layer; eval set grown to 200–500; AI and MCP (see sections 4 and 5).
- **M13–24:** Companies from EDGAR, GLEIF, Wikidata; annual DOI releases; JRC COIN-style methodology audit.
