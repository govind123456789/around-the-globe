# Page-level wireframes (low fidelity)

Desktop layouts shown at ~1200px. Mobile rule for all templates: single column, sticky search, tables become cards with the rank + score + one chosen column, map collapses behind a toggle. Every chart has a "View as table" control (WCAG).

**All names, numbers and ranks below are layout placeholders, not data.**

Chips used throughout:
`[SRC: World Bank · 2024]` source + observation year · `[CALC v1.2]` calculated by ranking engine · `[EST]` estimated · `[PROJ]` projected · `[AI]` AI-generated interpretation.

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
│ │ HDI  [OFFICIAL]│ │ NCI  [ORIGINAL]│ │ GDP per capita │ │ Life expectancy│  │
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
│ BUILD YOUR OWN INDEX  — pick indicators, set weights, see results  [Start →] │  (M5-6)
├──────────────────────────────────────────────────────────────────────────────┤
│ Footer: About · Methodology · Sources · Corrections · Editorial policy       │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. Ranking page `/rankings/{slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Rankings › Development                                                       │
│ Human Development Index                         [OFFICIAL · UNDP methodology] │
│ Edition: [HDR 2025 (2023 data) ▾]   Updated 2025-05-06   Coverage 191/193     │
│ [Share] [Embed] [Download CSV] [Methodology]                                  │
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
│ │ HDI  #134/193│ │ NCI  #… (r…) │ │ GDP  #5      │ │ GDP pc #…    │  more →  │
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
│ [M5-6] Ask about India: "Why has India's HDI rank changed since 2015?" [Ask] │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 4. Compare `/compare/{a}-vs-{b}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Compare: [🇨🇳 China ×] [🇮🇳 India ×] [+ Add up to 3 more]                      │
│ Lens: [All indicators ▾ | HDI | NCI | Economy | Health …]                    │
├──────────────────────────────────────────────────────────────────────────────┤
│ PILLAR CHART (radar or grouped bars, NCI pillars)        Table ⇄             │
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
│ [M5-6] AI EXPLAIN [AI] — "Biggest gaps and what drives them" (cited)         │
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
│ Used in rankings: HDI (health dimension) · NCI (human capital)               │
│ [Download CSV] [API call ⟨/⟩]                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 6. Methodology page `/methodology/{ranking-slug}`

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ National Capability Index — Methodology v1.0.0      [ORIGINAL — not official]│
│ Version [1.0.0 ▾] · Published 2026-… · Engine a1b2c3d · Inputs sha 9f…       │
├──────────────────────────────────────────────────────────────────────────────┤
│ 1 What it measures / what it does NOT measure                                │
│ 2 Eligibility (entity type, min population, coverage ≥ 70%)                  │
│ 3 Indicators & weights (table: pillar · indicator · weight · direction ·     │
│   transform · source)                                                         │
│ 4 Normalization & aggregation (KaTeX formula)                                │
│ 5 Missing data policy                                                         │
│ 6 Sensitivity analysis (chart: rank ranges for top 30)                       │
│ 7 Limitations (e.g. military pillar ≠ conflict outcome predictor)            │
│ 8 Change log across versions                                                  │
│ [Download full input snapshot]                                                │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 7. Index Builder `/index-builder/new` (M5-6)

```
┌───────────────────────────┬──────────────────────────────────────────────────┐
│ 1 ENTITY SET              │ LIVE PREVIEW                                     │
│  Countries ▾ · Region ▾   │  Rank │ Country │ Score │ Range │ Coverage       │
│ 2 INDICATORS  [+ Add]     │  1    │ …       │       │       │                │
│  ▸ R&D % GDP     w [20]%  │  2    │ …       │       │       │                │
│  ▸ Internet users w [15]% │  …                                               │
│  ▸ … (only indicators     │  ⚠ 23 countries excluded (coverage < 70%)        │
│    applicable to entity)  │                                                  │
│  Σ weights = 100% ✓       │  Sensitivity: top-10 stable in 94% of runs       │
│ 3 SETTINGS                │                                                  │
│  Normalize [min-max ▾]    │                                                  │
│  Aggregate [arith ▾]      │                                                  │
│  Missing [exclude ▾]      │                                                  │
│ [✨ Suggest from question]│                                                  │
│ ☐ I have reviewed the     │                                                  │
│   assumptions             │  [Save private]  [Publish link] (needs ☑)        │
└───────────────────────────┴──────────────────────────────────────────────────┘
```

## 8. AI Research `/ask` (M5-6)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Ask a question about the data                                                │
│ [ Compare India, China and Vietnam on manufacturing competitiveness…   ][Ask]│
├──────────────────────────────────────────────────────────────────────────────┤
│ ANSWER [AI]                                                                   │
│  Paragraph with figures, each with superscript citation ¹ ² ³                │
│  Chart produced from tool results                                            │
│  "What I couldn't answer": indicators with no data, years that don't align   │
├──────────────────────────────────────────────────────────────────────────────┤
│ EVIDENCE  ¹ obs #… Manufacturing VA % GDP, India, 2024 [WB]                  │
│           ² ranking NCI v1.0 pillar 'economic' …                             │
│ ▸ Show calculation trace (tool calls)                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```
