## What it measures

The Capability Index estimates a country's present capacity for long-term prosperity. It uses three pillars:

- **Economy**: how much the economy produces per person, whether people who want work can find it, and whether the basic infrastructure of electricity reaches everyone.
- **Innovation**: how much a country invests in research, how many people do research, how connected the population is, and how much of its manufacturing exports are high-technology.
- **Human capital**: how long people live and how much education they receive and can expect to receive.

## What it does not measure

- It is **not** a measure of national power, military strength or geopolitical influence. It contains no military indicators.
- It does not measure happiness, freedom, inequality, environmental sustainability or the quality of institutions. Those matter, but the open datasets for them either have licences that do not allow inclusion in a CC BY index (for example share-alike democracy data), or they need careful separate treatment.
- It describes recent levels, not momentum. A fast-improving country with a low starting point will score lower than a slow-moving rich one.
- It is relative. A score of 100 means "best among eligible countries on these indicators", not perfection.

## Why these weights

The weights are a judgement, published so you can disagree with them. Economy and innovation get 35% each because the index is about *capacity*: both production and the ability to create new products and knowledge. Human capital gets 30%, because health and education are also captured indirectly through the other two pillars. Within the Economy pillar, GDP per capita (PPP, log-scaled) dominates at 60%. Log scaling means a rise from $2,000 to $4,000 counts as much as a rise from $40,000 to $80,000.

To test the weights, the [sensitivity analysis](#calculation) randomly shifts every weight by up to ±25% a thousand times. Countries whose rank range is wide are sensitive to the weighting. Treat their exact position with caution. You can also try your own weights in the [Index Builder](/index-builder/#from=capability-index).

## Known limitations

- **Missing data.** R&D spending and researcher counts are missing for many lower-income countries. A country is ranked only if it has data for at least 70% of the weight, so some countries are not ranked, rather than being ranked on guesses.
- **Different years.** Each country's latest value from 2018 onward is used, so values can describe different years.
- **Small economies.** Countries under 500,000 people are left out. Their indicators (for example high-tech export shares) are often driven by a handful of firms.
- **Financial centres.** GDP per capita overstates living standards in economies with large foreign-owned profits.
- **Modelled estimates.** Unemployment uses ILO modelled estimates.
