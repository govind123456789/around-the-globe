-- =============================================================================
-- Free Global Rankings Platform — pipeline data model (v0.2)
-- Engine: DuckDB. Each table is written to Parquet per release:
--   r2://<bucket>/releases/YYYY-MM-DD/tables/<table>.parquet
-- Nothing is served from a database. Postgres is optional, local only.
--
-- Rules enforced here or in pipeline checks (pipeline/validate):
--   * Missing values are absent rows, never zeros.
--   * Every observation carries its source release and status.
--   * A release is a full snapshot; old releases are never modified.
--   * Ranking versions are immutable once published (CI compares against R2).
--   * Licence gate: see data/licences.yaml and the views at the bottom.
-- =============================================================================

CREATE TYPE entity_type   AS ENUM ('country', 'country_group', 'city', 'university', 'company', 'industry');
CREATE TYPE source_tier   AS ENUM ('green', 'amber', 'red', 'unverified');
CREATE TYPE obs_status    AS ENUM ('measured', 'estimate', 'forecast');
CREATE TYPE direction     AS ENUM ('higher_better', 'lower_better', 'neutral');
CREATE TYPE ranking_kind  AS ENUM ('official_reproduction', 'original_composite', 'single_indicator');
CREATE TYPE output_licence AS ENUM ('CC-BY-4.0', 'CC-BY-SA-4.0', 'ODbL-1.0');

-- ---------------------------------------------------------------------------
-- Sources & licences (loaded from data/licences.yaml)
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
  source_id         VARCHAR PRIMARY KEY,          -- 'wb-wdi', 'undp-hdr', 'ti-cpi'
  publisher         VARCHAR NOT NULL,
  title             VARCHAR NOT NULL,
  url               VARCHAR NOT NULL,
  licence           VARCHAR NOT NULL,             -- 'CC-BY-4.0', 'CC-BY-3.0-IGO', 'CC0', 'PD'
  licence_url       VARCHAR,
  tier              source_tier NOT NULL,
  commercial_ok     BOOLEAN NOT NULL,
  derivatives_ok    BOOLEAN NOT NULL,
  share_alike       BOOLEAN NOT NULL,
  no_modification   BOOLEAN NOT NULL DEFAULT false, -- e.g. TI CPI "not changed"
  attribution_text  VARCHAR NOT NULL,
  licence_checked_on DATE NOT NULL,
  notes             VARCHAR,
  CHECK (tier <> 'green' OR (commercial_ok AND derivatives_ok))
);

CREATE TABLE source_releases (
  source_release_id VARCHAR PRIMARY KEY,          -- 'wb-wdi@2026-11-08'
  source_id         VARCHAR NOT NULL REFERENCES sources(source_id),
  release_label     VARCHAR,                      -- publisher's label, e.g. 'HDR 2025'
  published_on      DATE,
  retrieved_at      TIMESTAMP NOT NULL,
  raw_path          VARCHAR NOT NULL,             -- r2 path of raw download
  checksum_sha256   VARCHAR NOT NULL,
  row_count         INTEGER,
  rejected_count    INTEGER NOT NULL DEFAULT 0
);

-- ---------------------------------------------------------------------------
-- Entities
-- ---------------------------------------------------------------------------
CREATE TABLE entities (
  entity_id     VARCHAR PRIMARY KEY,              -- 'IND' for countries; 'city:mumbai' etc. later
  type          entity_type NOT NULL,
  slug          VARCHAR NOT NULL,
  name          VARCHAR NOT NULL,
  iso3          VARCHAR,
  wikidata_qid  VARCHAR,
  parent_id     VARCHAR REFERENCES entities(entity_id),
  attributes    JSON,                             -- region, income group, capital QID …
  UNIQUE (type, slug),
  CHECK (iso3 IS NULL OR type = 'country')
);

CREATE TABLE entity_groups (                      -- membership in regions / income groups
  group_id   VARCHAR NOT NULL REFERENCES entities(entity_id),
  member_id  VARCHAR NOT NULL REFERENCES entities(entity_id),
  PRIMARY KEY (group_id, member_id)
);

-- ---------------------------------------------------------------------------
-- Indicators
-- ---------------------------------------------------------------------------
CREATE TABLE indicators (
  indicator_id   VARCHAR PRIMARY KEY,             -- 'gdp-per-capita-ppp'
  source_id      VARCHAR NOT NULL REFERENCES sources(source_id),
  source_code    VARCHAR,                         -- 'NY.GDP.PCAP.PP.CD'
  series_licence VARCHAR,                         -- WB per-series licence field, if different
  name           VARCHAR NOT NULL,
  definition     VARCHAR NOT NULL,
  unit           VARCHAR NOT NULL,
  direction      direction NOT NULL,
  dimension      VARCHAR NOT NULL,                -- 'economy', 'health' …
  applies_to     entity_type[] NOT NULL,          -- reuse infrastructure, not incompatible metrics
  transform      VARCHAR,                         -- 'log', null
  value_min      DOUBLE,                          -- plausible-range validation
  value_max      DOUBLE,
  decimals       TINYINT NOT NULL DEFAULT 2,
  display_only   BOOLEAN NOT NULL DEFAULT false   -- true => never an engine input (e.g. CPI)
);

-- ---------------------------------------------------------------------------
-- Observations
-- ---------------------------------------------------------------------------
CREATE TABLE observations (
  entity_id          VARCHAR NOT NULL REFERENCES entities(entity_id),
  indicator_id       VARCHAR NOT NULL REFERENCES indicators(indicator_id),
  year               SMALLINT NOT NULL,           -- observation year, not retrieval date
  value              DOUBLE NOT NULL,             -- missing = no row
  status             obs_status NOT NULL DEFAULT 'measured',
  source_release_id  VARCHAR NOT NULL REFERENCES source_releases(source_release_id),
  note               VARCHAR,
  PRIMARY KEY (entity_id, indicator_id, year)
);

CREATE TABLE validation_rejects (
  source_release_id VARCHAR NOT NULL,
  raw_row           JSON NOT NULL,
  rule              VARCHAR NOT NULL,             -- 'unknown_entity', 'out_of_range', 'unit_change'
  detail            VARCHAR
);

-- ---------------------------------------------------------------------------
-- Rankings (definitions loaded from data/rankings/*.yaml)
-- ---------------------------------------------------------------------------
CREATE TABLE rankings (
  ranking_id        VARCHAR NOT NULL,             -- 'human-development-index'
  version           VARCHAR NOT NULL,             -- semver
  kind              ranking_kind NOT NULL,
  name              VARCHAR NOT NULL,
  entity_type       entity_type NOT NULL,
  official_owner    VARCHAR,                      -- 'UNDP' for official reproductions
  eligibility_rule  JSON NOT NULL,                -- {"min_population": 100000}
  normalisation     VARCHAR NOT NULL,             -- 'min_max', 'min_max_goalposts', 'z_score'
  aggregation       VARCHAR NOT NULL,             -- 'arithmetic', 'geometric', 'pillars'
  min_coverage      DOUBLE NOT NULL DEFAULT 0.7,  -- share of total weight with data
  mc_runs           INTEGER NOT NULL DEFAULT 1000,
  mc_spread         DOUBLE NOT NULL DEFAULT 0.25,
  mc_seed           BIGINT NOT NULL,
  reference_year    SMALLINT NOT NULL,
  max_data_age      TINYINT NOT NULL DEFAULT 5,
  output_licence    output_licence NOT NULL DEFAULT 'CC-BY-4.0',
  methodology_path  VARCHAR NOT NULL,             -- content/methodology/<id>/<version>.md
  published_on      DATE,
  PRIMARY KEY (ranking_id, version),
  CHECK ((kind = 'official_reproduction') = (official_owner IS NOT NULL))
);

CREATE TABLE ranking_weights (
  ranking_id    VARCHAR NOT NULL,
  version       VARCHAR NOT NULL,
  pillar        VARCHAR,                          -- null for single-level indices
  pillar_weight DOUBLE,
  indicator_id  VARCHAR NOT NULL REFERENCES indicators(indicator_id),
  weight        DOUBLE NOT NULL CHECK (weight > 0 AND weight <= 1),  -- within pillar
  goalpost_min  DOUBLE,
  goalpost_max  DOUBLE,
  PRIMARY KEY (ranking_id, version, indicator_id),
  FOREIGN KEY (ranking_id, version) REFERENCES rankings(ranking_id, version)
);

CREATE TABLE ranking_results (
  ranking_id      VARCHAR NOT NULL,
  version         VARCHAR NOT NULL,
  entity_id       VARCHAR NOT NULL REFERENCES entities(entity_id),
  score           DOUBLE,                         -- null when not ranked
  rank            INTEGER,
  is_tied         BOOLEAN NOT NULL DEFAULT false,
  rank_low        INTEGER,                        -- Monte Carlo 5th percentile
  rank_high       INTEGER,                        -- Monte Carlo 95th percentile
  coverage        DOUBLE NOT NULL,
  excluded_reason VARCHAR,                        -- 'coverage_below_threshold', 'ineligible'
  pillar_scores   JSON,
  PRIMARY KEY (ranking_id, version, entity_id),
  FOREIGN KEY (ranking_id, version) REFERENCES rankings(ranking_id, version),
  CHECK ((score IS NULL) = (excluded_reason IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- Licence-gate views (CI fails if any of these return rows)
-- ---------------------------------------------------------------------------

-- 1. Non-green data in anything published
CREATE VIEW gate_non_green_published AS
SELECT DISTINCT o.indicator_id, s.source_id, s.tier
FROM observations o
JOIN indicators i USING (indicator_id)
JOIN sources s    ON s.source_id = i.source_id
WHERE s.tier <> 'green';

-- 2. Share-alike or no-modification inputs feeding a CC BY ranking
CREATE VIEW gate_licence_leak_into_composite AS
SELECT r.ranking_id, r.version, w.indicator_id, s.source_id, s.share_alike, s.no_modification
FROM rankings r
JOIN ranking_weights w USING (ranking_id, version)
JOIN indicators i      ON i.indicator_id = w.indicator_id
JOIN sources s         ON s.source_id = i.source_id
WHERE r.output_licence = 'CC-BY-4.0'
  AND (s.share_alike OR s.no_modification OR i.display_only);

-- 3. Indicator used for an entity type it does not apply to
CREATE VIEW gate_inapplicable_indicator AS
SELECT r.ranking_id, r.version, w.indicator_id, r.entity_type
FROM rankings r
JOIN ranking_weights w USING (ranking_id, version)
JOIN indicators i      ON i.indicator_id = w.indicator_id
WHERE NOT list_contains(i.applies_to, r.entity_type);

-- 4. Weights that don't sum to 1 (within each pillar, and across pillars)
CREATE VIEW gate_bad_weights AS
SELECT ranking_id, version, pillar, sum(weight) AS total
FROM ranking_weights
GROUP BY ALL
HAVING abs(sum(weight) - 1) > 1e-9
UNION ALL
SELECT ranking_id, version, '<pillars>' AS pillar, sum(pw) AS total
FROM (SELECT DISTINCT ranking_id, version, pillar, pillar_weight AS pw
      FROM ranking_weights WHERE pillar IS NOT NULL)
GROUP BY ALL
HAVING abs(sum(pw) - 1) > 1e-9;
