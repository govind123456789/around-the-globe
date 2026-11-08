# Around the Globe — free global rankings platform

Static-first build: a Python pipeline downloads open data, validates it, runs the licence gate,
computes rankings and renders a fully static site into `dist/`. Plan and specs live in `docs/`.

## Build and preview

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pipeline.build              # fetch (cached in raw/) + data + site
.venv/Scripts/python -m pipeline.build --site-only  # re-render pages from the last data build
.venv/Scripts/python -m http.server 8000 -d dist    # open http://localhost:8000
```

Node.js (`npx`) is also needed once, to simplify the map boundaries with mapshaper. The map uses Natural
Earth's India point-of-view edition, which shows boundaries as the Government of India depicts them.

`--strict` fails the build if any source's `licence_checked_on` is unset (use for public releases).

## Layout

- `data/` — `indicators.yaml`, `rankings.yaml`, `licences.yaml`, `site.yaml` (brand name, curated compare pairs)
- `pipeline/` — `fetch.py`, `build_data.py` (validation, licence gate, rankings, JSON/CSV/Parquet export), `engine.py`, `build_site.py`, `svg.py`, `schema.sql`
- `site/templates/`, `site/static/` — Jinja templates, CSS, client JS (`engine.js` is a port of `engine.py`)
- `content/` — methodology and about pages (Markdown)
- `dist/` — deployable output, including the static JSON API under `dist/v1/`

## Tests and deployment

```bash
.venv/Scripts/python -m pytest -q pipeline/tests     # engine, licence gate, JS/Python parity, history, built release
npx wrangler@4 deploy                                 # publish dist/ to Cloudflare (run `npx wrangler login` first)
```

- The live site is https://around-the-globe.round-the-globe.workers.dev (Cloudflare Workers, free plan). `vercel.json` only
  switches off Vercel's Git builds; the site is not deployed to Vercel.
- `wrangler.jsonc` serves `dist/` as Workers static assets (free plan: 20,000 files, 25 MiB each; a test enforces both).
- `.github/workflows/ci.yml` runs the tests on every push; `build-and-deploy.yml` rebuilds the data weekly with
  `--strict` and deploys. It needs repository secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`.
- Data stories (`pipeline/stories.py`) are generated from the release. They stay drafts (noindex, not in the
  sitemap) until `data/stories.yaml` marks them `published` after editorial review.

## Still to do

- Trademark check for "Around the Globe" and a matching domain (`data/site.yaml`).
- Create the Cloudflare account, add the secrets, and run the first deploy. `base_url` in `data/site.yaml` must be the real
  domain first: embed code, share cards and the sitemap all use it.
- Editorial review of the three draft stories; outside reviewers (journalist, economist, student, data engineer, policy analyst).
- Older releases are not kept once CI rebuilds `dist/`; mirror releases to R2 or Hugging Face before promising permanent URLs.
- Post-launch: live AI assistant + MCP server, batch AI summaries, universities (OpenAlex) and cities (GHSL), funding.

## Sources

World Bank WDI (per-series licence checked on every fetch) and Worldwide Governance Indicators,
UNDP HDR 2025 (HDI, IHDI, GDI, GII, PHDI and components), UN World Population Prospects 2024 (median age, projections to 2100), OECD (tax revenue, average wages), Transparency International CPI
(display only, via Our World in Data's republication), GDELT 1.0 daily event files (news volume and tone,
every third day over the last 90 days; `python -m pipeline.fetch --skip-gdelt` skips this ~210 MB download),
Wikidata (FIPS→ISO code mapping), Natural Earth (India point-of-view boundaries).

## Site features worth knowing

- **Names and flags:** `data/country_names.yaml` holds plain display names; flags are from flag-icons (MIT, `site/static/flags/`).
- **World page and live estimates:** `pipeline/live.py` and `site/static/js/live.js` extrapolate from published annual figures. They are labelled as estimates, and `/methodology/live-estimates/` explains the sums.
- **Question tabs:** `data/country_questions.yaml` lists each question's measures, wording and caveat.
- **Wide ranking tables:** add `columns` to a ranking in `data/rankings.yaml`.
- **Globe:** `site/static/js/globe.js` is decorative. It stays still for reduced-motion users and stops rotating on slow devices.

- **Index Builder rank ranges:** `sensitivity` in `engine.js` shakes every weight by up to ±25% over 200 seeded runs, after the sliders stop.
- **Embeds:** `/embed/rankings/<id>/` is a standalone top-10 chart (noindex, not in the sitemap); the Embed button copies the iframe code.
- **Share cards:** `pipeline/og.py` draws 1200×630 PNGs into `dist/og/` with Pillow, using the fonts in `site/assets/og-fonts/`.
- **No third parties at runtime:** fonts (`site/static/fonts/`) and MapLibre (`site/static/vendor/`) are self-hosted; a test enforces it.
- **Analytics:** off by default. Put a Cloudflare Web Analytics token in `cloudflare_analytics_token` in `data/site.yaml` to switch on the cookieless beacon.

## Country history pages (`/countries/<slug>/history/`)

Built by `pipeline/history.py` from:
- **Cliopatria** v0.2.1 (Seshat, CC BY 4.0): polity borders overlaid on today's borders every 5 years
  from 200 BCE (~2 min, cached in `build/history_shares.json`; reruns when its inputs or `history.py` change).
  Map snapshots every 50 years go to `dist/history/map/<year>.json`.
- **Wikidata** (CC0): wars, rebellions, revolutions, coups with a date and a location.
- **UCDP** v26.1 (CC BY 4.0): armed conflicts since 1946, battle deaths since 1989.
- **Maddison Project Database 2023** (CC BY 4.0): long-run GDP per capita and population.

A consistency check hides Cliopatria rows that outlive independence (e.g. a French row still covering
Algeria after 1962). Real overlaps it would wrongly hide are kept via `data/history_overrides.yaml`.
Each page discloses how many samples were hidden. Historical borders are approximate. Misleading Cliopatria
labels are corrected for display through `rename:` in the same file; their dates and borders stay as published.
