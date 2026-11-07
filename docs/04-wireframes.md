# Page-level wireframes (low fidelity) — v0.2

v0.2 changes: no accounts and no paid features. The Index Builder runs in the browser with its state in the URL. The flagship composite replaces the NCI and has no military pillar. The AI assistant has quota and breaker states. Every page is static and reads release JSON.

Desktop layouts shown at ~1200px. Mobile rule for all templates: single column, sticky search, tables become cards with the rank + score + one chosen column, map collapses behind a toggle. Every chart has a "View as table" control (WCAG).

**All names, numbers and ranks below are layout placeholders, not data.**

Chips used throughout:
`[SRC: World Bank · 2024]` source + observation year · `[CALC v1.2]` calculated by ranking engine · `[EST]` estimated · `[FCST]` forecast · `[AI]` AI-generated interpretation · `[CC BY]` licence of the shown data.

---

## 1. Home `/`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ LOGO   Explore  Rankings  Compare  Topics  Insights  Index Builder  Data  [🔍]│
├──────────────────────────────────────────────────────────────────────────────┤
│             Measure anything. Compare everything. Understand why.            │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ 🔍  Search a country, indicator or ranking…  e.g. "india vs china"   │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│   Try: Human Development Index · GDP per capita · Life expectancy            │
├──────────────────────────────────────────────────────────────────────────────┤
│ FEATURED RANKINGS                                              See all →     │
│ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐  │
│ │ HDI  [OFFICIAL]│ │ Flagship [ORIG]│ │ GDP per capita │ │ Life expectancy│  │
│ │ UNDP · 2023 data│ │ 2026 ed · v1.0 │ │ WB · 2024 data │ │ WB · 2023 data │  │
│ │ 1 Country A    │ │ 1 …            │ │ 1 …            │ │ 1 …            │  │
│ │ 2 Country B    │ │ 2 …            │ │ 2 …            │ │ 2 …            │  │
│ │ 3 Country C    │ │ 3 …            │ │ 3 …            │ │ 3 …            │  │
│ └────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘  │
├───────────────────────────────────────────────┬──────────────────────────────┤
│ WORLD MAP                [Indicator ▾] [Year ▾]│ COMPARE ANYTHING             │
│                                               │ [Country A ▾] vs [Country B ▾]│
│         (choropleth, hover = value+year)      │ [ Compare → ]                │
│                                               │ Trending: India vs China ·   │
│  legend ▓▓▓▓▓░░░  grey = no data              │ USA vs China · Japan vs Korea│
├───────────────────────────────────────────────┴──────────────────────────────┤
│ WHAT'S CHANGING                                                               │
│ • Insight card (title, 1-line dek, chart thumb, date)  × 3                    │
│ • Recently updated: "WDI release 2026-07 — 34 indicators refreshed"           │
├──────────────────────────────────────────────────────────────────────────────┤
│ BUILD YOUR OWN INDEX  — pick indicators, set weights, see results  [Start →] │
├──────────────────────────────────────────────────────────────────────────────┤
│ Footer: About · Methodology · Sources · Errata · Editorial policy · Licences │
│         Funding · Donate · "Data CC BY 4.0 · Code AGPL-3.0"                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. Ranking page `/rankings/{slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Rankings › Development                                                       │
│ Human Development Index                         [OFFICIAL · UNDP methodology] │
│ Edition: [HDR 2025 (2023 data) ▾]   Updated 2025-05-06   Coverage 191/193     │
│ [Share] [Embed] [Download CSV · CC BY] [Methodology] [JSON API]               │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Table | Map]   Region [All ▾] Income [All ▾] Min coverage [70% ▾] 🔍 filter │
├────┬──────┬─────────────────┬────────┬──────────┬──────────┬────────────────┤
│Rank│ Δ    │ Country         │ Score  │ Range*   │ Coverage │ Pillars ▸      │
├────┼──────┼─────────────────┼────────┼──────────┼──────────┼────────────────┤
│ 1  │ ▲1   │ Country A       │ 0.9xx  │ 1–2      │ 100%     │ ▮▮▮            │
│ =2 │ ▼1   │ Country B       │ 0.9xx  │ 1–3      │ 100%     │ ▮▮▮            │
│ …  │      │                 │        │          │          │                │
│ —  │      │ Country Z       │ n/a    │          │ 33%      │ Insufficient   │
│    │      │                 │        │          │          │ data — why?    │
├────┴──────┴─────────────────┴────────┴──────────┴──────────┴────────────────┤
│ * Range = 5th–95th percentile rank under ±25% weight changes (CALC).         │
│   Only shown for original composites; official indices show official rank.   │
├───────────────────────────────────────┬──────────────────────────────────────┤
│ HOW THIS IS CALCULATED                │ BIGGEST MOVERS SINCE LAST EDITION    │
│ HDI = (I_health·I_edu·I_income)^(1/3) │ ▲ Country X +7  ▼ Country Y −5       │
│ 3 dimensions · 4 indicators           │                                      │
│ Full methodology →                    │ HISTORY → (rank over editions)       │
├───────────────────────────────────────┴──────────────────────────────────────┤
│ Sources: UNDP HDR 2025 (CC BY 3.0 IGO) · Report a data issue                 │
└──────────────────────────────────────────────────────────────────────────────┘
Row click → expands inline: pillar scores, indicator values with [SRC · year] chips,
"Open profile" and "Compare with…" buttons.
```

## 3. Country profile `/countries/{slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 🇮🇳 India                               [Compare with… ▾]  [Share]           │
│ South Asia · Lower-middle income · Pop. 1.44 bn [SRC: WB · 2024]             │
│ Data freshness: 41 of 46 indicators updated within source schedule           │
├──────────────────────────────────────────────────────────────────────────────┤
│ WHERE INDIA RANKS                                                            │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│ │ HDI  #…/193  │ │ Flagship #…  │ │ GDP  #5      │ │ GDP pc #…    │  more →  │
│ │ ▲ 2          │ │ [ORIGINAL]   │ │ [SRC WB 2024]│ │              │          │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘          │
├──────────────────────────────────────────────────────────────────────────────┤
│ [Economy] [Human development] [Health] [Education] [Technology] [Energy] …   │
│ ── Economy ───────────────────────────────── [Absolute | Per capita] toggle  │
│ ┌──────────────────────────┬──────────────────────────┬────────────────────┐ │
│ │ GDP (current US$)        │ GDP growth               │ Inflation (CPI)    │ │
│ │ 3.9 tn   [SRC WB · 2024] │ 6.5%   [SRC WB · 2024]   │ 4.9% [SRC · 2024]  │ │
│ │ ╱╲╱──╱  20-yr sparkline  │ ╲╱╲╱─                    │ ─╲╱╲               │ │
│ │ World percentile: 97th   │ 88th                     │ (lower is better)  │ │
│ └──────────────────────────┴──────────────────────────┴────────────────────┘ │
│ See all Economy indicators →                                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│ RELATED: South Asia peers · Region profile · [M7-9: capital, cities, unis]   │
│ RELATED INSIGHTS: card × 2                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ SUMMARY [AI] — batch-generated per release; every figure links to its value  │
│ "…GDP per capita rose x% between 2015 and 2024 ¹ …"   Generated <date>       │
├──────────────────────────────────────────────────────────────────────────────┤
│ [M5-6] Ask about India: "Why has India's HDI rank changed since 2015?" [Ask] │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 4. Compare `/compare/{a}-vs-{b}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Compare: [🇨🇳 China ×] [🇮🇳 India ×] [+ Add up to 3 more]                      │
│ Lens: [All indicators ▾ | HDI | Flagship | Economy | Health …]                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ PILLAR CHART (radar or grouped bars, Flagship pillars)   Table ⇄             │
├──────────────────────────────────────────────────────────────────────────────┤
│ Indicator                    │ China            │ India            │ Gap     │
│──────────────────────────────┼──────────────────┼──────────────────┼─────────│
│ GDP per capita, PPP          │ 25,0xx  [WB 2024]│ 10,1xx  [WB 2024]│ 2.5×    │
│ Life expectancy              │ 78.x    [WB 2023]│ 72.x    [WB 2023]│ +6.x yr │
│ R&D spend % GDP              │ 2.4     [WB 2022]│ 0.6     [WB 2020]│ ⚠ years │
│                              │                  │                  │ differ  │
│ … grouped by dimension, collapsible                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ OVER TIME: [indicator ▾] line chart, both entities, 2000–latest              │
├──────────────────────────────────────────────────────────────────────────────┤
│ [M5-6] AI EXPLAIN [AI] — curated pairs: batch-generated; others: live, quota │
│ [Download comparison CSV] [Share] [Embed]                                     │
└──────────────────────────────────────────────────────────────────────────────┘
Rule: when entity years differ for an indicator, show ⚠ and offer "latest common year".
```

## 5. Indicator page `/data/indicators/{slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Life expectancy at birth (years)                       [Higher is better]    │
│ Definition … · Source: World Bank WDI (SP.DYN.LE00.IN) · Licence CC BY 4.0   │
│ Coverage: 2023 — 198/217 entities · 1960–2023                                 │
├───────────────────────────────────────────────┬──────────────────────────────┤
│ MAP [Year slider ─────●──]                     │ TOP / BOTTOM 10              │
├───────────────────────────────────────────────┴──────────────────────────────┤
│ TIME SERIES: pick up to 10 entities                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Used in rankings: HDI (health dimension) · Flagship (human cap.)             │
│ [Download CSV] [API call ⟨/⟩]                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 6. Methodology page `/methodology/{ranking-slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Flagship Composite Index — Methodology v1.0.0       [ORIGINAL — not official]│
│ Version [1.0.0 ▾] · Published 2026-… · Engine a1b2c3d · Inputs sha 9f…       │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1 What it measures / what it does NOT measure                                │
│ 2 Eligibility (entity type, min population, coverage ≥ 70%)                  │
│ 3 Indicators & weights (table: pillar · indicator · weight · direction ·     │
│   transform · source)                                                         │
│ 4 Normalization & aggregation (KaTeX formula)                                │
│ 5 Missing data policy                                                         │
│ 6 Sensitivity analysis (chart: rank ranges for top 30)                       │
│ 7 Limitations (what the index cannot say; sources excluded and why)         │
│ 8 Change log across versions                                                  │
│ 9 Input licences; sources excluded by the licence gate                       │
│ [Download full input snapshot · CC BY 4.0]                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 7. Index Builder `/index-builder#…` (v1, browser only)

```
┌───────────────────────────┬──────────────────────────────────────────────────┐
│ 1 ENTITY SET              │ LIVE PREVIEW (computed in the browser)           │
│  Countries ▾ · Region ▾   │  Rank │ Country │ Score │ Range │ Coverage       │
│ 2 INDICATORS  [+ Add]     │  1    │ …       │       │       │                │
│  ▸ R&D % GDP     w [20]%  │  2    │ …       │       │       │                │
│  ▸ Internet users w [15]% │  …                                               │
│  ▸ … (CC BY-compatible,   │  ⚠ 23 countries not ranked (coverage < 70%)      │
│    applicable only; CPI   │                                                  │
│    and SA layers hidden)  │  Sensitivity: top-10 stable in 94% of runs       │
│  Σ weights = 100% ✓       │                                                  │
│ 3 SETTINGS                │                                                  │
│  Normalise [min-max ▾]    │                                                  │
│  Aggregate [arith ▾]      │                                                  │
│  Coverage ≥ [70%]         │                                                  │
│ Start from: [Study abroad]│                                                  │
│  [Market entry][Relocate] │  [Copy link]  [Export CSV · inherits licences]   │
└───────────────────────────┴──────────────────────────────────────────────────┘
State lives in the URL fragment (#e=country&i=rd:20,inet:15&n=minmax…); nothing is sent to a server.
Footer note: "Your index inherits the licences of its sources. It is not an official ranking."
```

## 8. AI assistant `/ask` (M5-6)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Ask a question about the data                    [Turnstile check, invisible]│
│ [ Compare India, China and Vietnam on R&D and internet access…         ][Ask]│
│ 3 of 5 questions left today · Use your own API key ▸ (stored in browser)     │
├──────────────────────────────────────────────────────────────────────────────┤
│ ANSWER [AI]   (served from cache ⚡ / generated)                              │
│  Paragraph with figures, each with a superscript citation ¹ ² ³               │
│  Chart built from tool results                                               │
│  "What I couldn't answer": indicators with no data, years that don't align   │
├──────────────────────────────────────────────────────────────────────────────┤
│ EVIDENCE  ¹ R&D % GDP, India, 2022 [WB WDI · CC BY]  → /countries/india     │
│           ² Flagship v1.0 pillar 'innovation' …                              │
│ ▸ Show tool calls                                                            │
└──────────────────────────────────────────────────────────────────────────────┘

BREAKER STATE (daily budget reached or provider unavailable):
┌──────────────────────────────────────────────────────────────────────────────┐
│ The live assistant has reached today's limit. It resets at 00:00 UTC.       │
│ Meanwhile: precomputed summaries for India · China · Vietnam →               │
│ Compare these countries → · Use your own API key ▸                           │
└──────────────────────────────────────────────────────────────────────────────┘
```
