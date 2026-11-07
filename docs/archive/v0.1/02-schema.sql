-- =============================================================================
-- Global Rankings & Intelligence Platform — initial PostgreSQL schema (v0.1)
-- Target: PostgreSQL 16+. Requires extensions: pg_trgm, citext.
--
-- Design rules enforced here:
--   * Observations are append-only; revisions supersede, never overwrite.
--   * Ranking versions are immutable once published (trigger at bottom).
--   * Missing values are absent rows, never zeros.
--   * Every observation carries source release + observation period + status.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------------
CREATE TYPE entity_type AS ENUM (
  'country', 'country_group', 'subnational_region', 'city',
  'university', 'company', 'industry', 'product', 'public_institution'
);

CREATE TYPE observation_status AS ENUM (
  'measured', 'estimated', 'projected', 'modelled', 'imputed'
);

CREATE TYPE indicator_direction AS ENUM ('higher_is_better', 'lower_is_better', 'neutral');

CREATE TYPE normalization_method AS ENUM (
  'min_max', 'min_max_goalposts', 'z_score', 'rank_percentile', 'log_min_max', 'none'
);

CREATE TYPE aggregation_method AS ENUM (
  'weighted_arithmetic', 'weighted_geometric', 'pillar_of_pillars', 'official_custom'
);

CREATE TYPE missing_data_policy AS ENUM ('exclude_entity', 'reweight_available', 'fail');

CREATE TYPE ranking_kind AS ENUM ('official_reproduction', 'original_composite', 'single_indicator', 'user_custom');

CREATE TYPE publication_status AS ENUM ('draft', 'in_review', 'published', 'retired');

CREATE TYPE relationship_type AS ENUM (
  'member_of', 'capital_of', 'located_in', 'subsidiary_of', 'operates_in', 'part_of'
);

-- ---------------------------------------------------------------------------
-- Entities
-- ---------------------------------------------------------------------------
CREATE TABLE entities (
  id               bigserial PRIMARY KEY,
  type             entity_type NOT NULL,
  slug             citext NOT NULL,                     -- 'india', 'mumbai'
  name             text NOT NULL,
  short_name       text,
  iso3             char(3),                             -- countries only
  wikidata_qid     text,                                -- cross-reference, not authority
  external_ids     jsonb NOT NULL DEFAULT '{}',         -- {"worldbank":"IND","undp":"IND"}
  attributes       jsonb NOT NULL DEFAULT '{}',         -- flag, region label, etc.
  is_active        boolean NOT NULL DEFAULT true,
  valid_from       date,                                -- e.g. state formation
  valid_to         date,                                -- e.g. dissolution
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  search_tsv       tsvector GENERATED ALWAYS AS (
                     to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(short_name,''))
                   ) STORED,
  UNIQUE (type, slug),
  CONSTRAINT iso3_only_for_countries CHECK (iso3 IS NULL OR type = 'country')
);
CREATE UNIQUE INDEX entities_iso3_uq ON entities (iso3) WHERE iso3 IS NOT NULL;
CREATE INDEX entities_search_idx ON entities USING gin (search_tsv);
CREATE INDEX entities_name_trgm_idx ON entities USING gin (name gin_trgm_ops);

CREATE TABLE entity_aliases (
  entity_id  bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  alias      text NOT NULL,
  lang       text NOT NULL DEFAULT 'en',
  PRIMARY KEY (entity_id, alias, lang)
);
CREATE INDEX entity_aliases_trgm_idx ON entity_aliases USING gin (alias gin_trgm_ops);

CREATE TABLE entity_relationships (
  id            bigserial PRIMARY KEY,
  from_entity   bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  to_entity     bigint NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  relationship  relationship_type NOT NULL,
  valid_from    date,
  valid_to      date,
  source_id     bigint,                                 -- FK added after sources
  UNIQUE (from_entity, to_entity, relationship, valid_from)
);

-- ---------------------------------------------------------------------------
-- Sources & licensing
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
  id                    bigserial PRIMARY KEY,
  slug                  citext UNIQUE NOT NULL,         -- 'world-bank-wdi', 'undp-hdr'
  publisher             text NOT NULL,
  title                 text NOT NULL,
  homepage_url          text,
  licence_name          text NOT NULL,                  -- 'CC BY 4.0'
  licence_url           text,
  attribution_text      text NOT NULL,
  allows_redistribution boolean NOT NULL,
  allows_commercial_use boolean NOT NULL,
  licence_notes         text,
  licence_reviewed_at   date,                           -- null = not yet reviewed => no exports
  update_schedule       text,                           -- 'annual', 'quarterly', cron-ish
  created_at            timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE entity_relationships
  ADD CONSTRAINT entity_relationships_source_fk FOREIGN KEY (source_id) REFERENCES sources(id);

CREATE TABLE source_releases (
  id               bigserial PRIMARY KEY,
  source_id        bigint NOT NULL REFERENCES sources(id),
  release_label    text NOT NULL,                       -- 'HDR 2025', 'WDI 2026-07'
  published_at     date,                                -- publisher's release date
  retrieved_at     timestamptz NOT NULL DEFAULT now(),
  raw_artifact_uri text,                                -- object-storage path of raw download
  raw_sha256       char(64),
  row_count        integer,
  rejected_count   integer NOT NULL DEFAULT 0,
  ingestion_log    jsonb NOT NULL DEFAULT '{}',
  UNIQUE (source_id, release_label)
);

-- ---------------------------------------------------------------------------
-- Taxonomy & indicators
-- ---------------------------------------------------------------------------
CREATE TABLE dimensions (                               -- Level 2: Economy, Safety ...
  id          serial PRIMARY KEY,
  slug        citext UNIQUE NOT NULL,
  name        text NOT NULL,
  description text,
  parent_id   integer REFERENCES dimensions(id),
  sort_order  integer NOT NULL DEFAULT 0
);

CREATE TABLE indicators (                               -- Level 3
  id                 bigserial PRIMARY KEY,
  slug               citext UNIQUE NOT NULL,            -- 'gdp-per-capita-ppp'
  name               text NOT NULL,
  short_name         text,
  definition         text NOT NULL,
  unit               text NOT NULL,                     -- 'current international $'
  unit_multiplier    numeric NOT NULL DEFAULT 1,
  direction          indicator_direction NOT NULL,
  dimension_id       integer NOT NULL REFERENCES dimensions(id),
  primary_source_id  bigint REFERENCES sources(id),
  source_code        text,                              -- 'NY.GDP.PCAP.PP.CD'
  is_per_capita      boolean NOT NULL DEFAULT false,
  absolute_counterpart_id bigint REFERENCES indicators(id),
  value_min          numeric,                           -- validation bounds
  value_max          numeric,
  decimals           smallint NOT NULL DEFAULT 2,
  created_at         timestamptz NOT NULL DEFAULT now(),
  search_tsv         tsvector GENERATED ALWAYS AS (
                       to_tsvector('english', coalesce(name,'') || ' ' || coalesce(definition,''))
                     ) STORED
);
CREATE INDEX indicators_search_idx ON indicators USING gin (search_tsv);
CREATE INDEX indicators_name_trgm_idx ON indicators USING gin (name gin_trgm_ops);

-- Which entity types an indicator is valid for ("reuse infrastructure, not metrics")
CREATE TABLE indicator_applicability (
  indicator_id bigint NOT NULL REFERENCES indicators(id) ON DELETE CASCADE,
  entity_type  entity_type NOT NULL,
  notes        text,
  PRIMARY KEY (indicator_id, entity_type)
);

-- ---------------------------------------------------------------------------
-- Observations (append-only)
-- ---------------------------------------------------------------------------
CREATE TABLE observations (
  id                 bigserial PRIMARY KEY,
  entity_id          bigint NOT NULL REFERENCES entities(id),
  indicator_id       bigint NOT NULL REFERENCES indicators(id),
  period_start       date NOT NULL,                     -- observation period, not retrieval date
  period_end         date NOT NULL,
  period_label       text NOT NULL,                     -- '2024', '2024-Q3'
  value              numeric NOT NULL,                  -- missing = no row
  status             observation_status NOT NULL DEFAULT 'measured',
  lower_bound        numeric,                           -- uncertainty interval when source gives one
  upper_bound        numeric,
  source_release_id  bigint NOT NULL REFERENCES source_releases(id),
  source_note        text,
  superseded_by      bigint REFERENCES observations(id),
  superseded_at      timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (period_end >= period_start),
  CHECK (lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound)
);
-- Only one current value per entity/indicator/period/source release lineage
CREATE UNIQUE INDEX observations_current_uq
  ON observations (entity_id, indicator_id, period_start, period_end)
  WHERE superseded_at IS NULL;   -- supersede: set old.superseded_at, insert new, then set old.superseded_by
CREATE INDEX observations_lookup_idx ON observations (indicator_id, period_end DESC, entity_id);
CREATE INDEX observations_entity_idx ON observations (entity_id, indicator_id, period_end DESC);
CREATE INDEX observations_release_idx ON observations (source_release_id);

CREATE VIEW current_observations AS
  SELECT * FROM observations WHERE superseded_at IS NULL;

CREATE VIEW latest_observations AS
  SELECT DISTINCT ON (entity_id, indicator_id) *
  FROM observations
  WHERE superseded_at IS NULL
  ORDER BY entity_id, indicator_id, period_end DESC;

-- Rows that failed validation, kept for the admin quality report
CREATE TABLE ingestion_rejects (
  id                bigserial PRIMARY KEY,
  source_release_id bigint NOT NULL REFERENCES source_releases(id),
  raw_row           jsonb NOT NULL,
  reason            text NOT NULL,
  created_at        timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Rankings (Level 4)
-- ---------------------------------------------------------------------------
CREATE TABLE rankings (
  id              bigserial PRIMARY KEY,
  slug            citext UNIQUE NOT NULL,               -- 'human-development-index'
  name            text NOT NULL,
  kind            ranking_kind NOT NULL,
  entity_type     entity_type NOT NULL,
  summary         text NOT NULL,
  official_owner  text,                                 -- 'UNDP' for official reproductions
  owner_user_id   bigint,                               -- set for user_custom (FK below)
  is_public       boolean NOT NULL DEFAULT true,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK ((kind = 'official_reproduction') = (official_owner IS NOT NULL))
);

CREATE TABLE ranking_versions (
  id                    bigserial PRIMARY KEY,
  ranking_id            bigint NOT NULL REFERENCES rankings(id),
  version               text NOT NULL,                  -- semver '1.0.0'
  edition_label         text NOT NULL,                  -- '2026 edition'
  status                publication_status NOT NULL DEFAULT 'draft',
  reference_period_end  date NOT NULL,                  -- latest observation year allowed
  max_data_age_years    smallint NOT NULL DEFAULT 5,
  eligibility_rules     jsonb NOT NULL DEFAULT '{}',    -- {"min_population":100000,"groups":["..."]}
  normalization         normalization_method NOT NULL,
  aggregation           aggregation_method NOT NULL,
  missing_policy        missing_data_policy NOT NULL,
  min_coverage          numeric NOT NULL DEFAULT 0.7 CHECK (min_coverage BETWEEN 0 AND 1),
  sensitivity_runs      integer NOT NULL DEFAULT 1000,
  sensitivity_spread    numeric NOT NULL DEFAULT 0.25,
  engine_version        text,                           -- git sha of scoring engine
  input_snapshot_sha256 char(64),                       -- hash of exact observation ids used
  methodology_doc_id    bigint,                         -- FK below
  change_notes          text,
  published_at          timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ranking_id, version)
);

-- Pillars (sub-indices) allow two-level weighting
CREATE TABLE ranking_pillars (
  id                  bigserial PRIMARY KEY,
  ranking_version_id  bigint NOT NULL REFERENCES ranking_versions(id) ON DELETE CASCADE,
  slug                text NOT NULL,
  name                text NOT NULL,
  weight              numeric NOT NULL CHECK (weight > 0 AND weight <= 1),
  aggregation         aggregation_method NOT NULL DEFAULT 'weighted_arithmetic',
  sort_order          integer NOT NULL DEFAULT 0,
  UNIQUE (ranking_version_id, slug)
);

CREATE TABLE ranking_indicators (
  id                  bigserial PRIMARY KEY,
  ranking_version_id  bigint NOT NULL REFERENCES ranking_versions(id) ON DELETE CASCADE,
  pillar_id           bigint REFERENCES ranking_pillars(id) ON DELETE CASCADE,
  indicator_id        bigint NOT NULL REFERENCES indicators(id),
  weight              numeric NOT NULL CHECK (weight > 0 AND weight <= 1),  -- within pillar
  direction_override  indicator_direction,
  transform           text,                             -- 'log', 'cap_at:75000', null
  goalpost_min        numeric,
  goalpost_max        numeric,
  UNIQUE (ranking_version_id, indicator_id)
);

-- Exact observations used by a version (reproducibility)
CREATE TABLE ranking_inputs (
  ranking_version_id  bigint NOT NULL REFERENCES ranking_versions(id) ON DELETE CASCADE,
  observation_id      bigint NOT NULL REFERENCES observations(id),
  PRIMARY KEY (ranking_version_id, observation_id)
);

CREATE TABLE ranking_results (
  ranking_version_id  bigint NOT NULL REFERENCES ranking_versions(id) ON DELETE CASCADE,
  entity_id           bigint NOT NULL REFERENCES entities(id),
  score               numeric,                          -- null when excluded
  rank                integer,
  is_tied             boolean NOT NULL DEFAULT false,
  coverage            numeric NOT NULL CHECK (coverage BETWEEN 0 AND 1),
  indicators_used     smallint NOT NULL,
  excluded_reason     text,                             -- 'coverage_below_threshold'
  rank_p05            integer,                          -- sensitivity rank interval
  rank_p95            integer,
  pillar_scores       jsonb NOT NULL DEFAULT '{}',      -- {"economic": 71.2, ...}
  indicator_scores    jsonb NOT NULL DEFAULT '{}',      -- normalized z_ij per indicator
  PRIMARY KEY (ranking_version_id, entity_id),
  CHECK ((score IS NULL) = (excluded_reason IS NOT NULL))
);
CREATE INDEX ranking_results_rank_idx ON ranking_results (ranking_version_id, rank);

-- ---------------------------------------------------------------------------
-- Methodology & editorial content
-- ---------------------------------------------------------------------------
CREATE TABLE methodology_documents (
  id            bigserial PRIMARY KEY,
  slug          citext UNIQUE NOT NULL,
  title         text NOT NULL,
  body_md       text NOT NULL,                          -- Markdown + KaTeX
  limitations_md text NOT NULL,
  version       text NOT NULL,
  status        publication_status NOT NULL DEFAULT 'draft',
  published_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE ranking_versions
  ADD CONSTRAINT ranking_versions_methodology_fk FOREIGN KEY (methodology_doc_id) REFERENCES methodology_documents(id);

CREATE TABLE topics (
  id          serial PRIMARY KEY,
  slug        citext UNIQUE NOT NULL,                   -- 'economy', 'military'
  name        text NOT NULL,
  description text,
  dimension_id integer REFERENCES dimensions(id)
);

CREATE TABLE analysis_reports (
  id             bigserial PRIMARY KEY,
  slug           citext UNIQUE NOT NULL,
  title          text NOT NULL,
  dek            text,
  body_md        text NOT NULL,
  author_name    text NOT NULL,
  ai_assisted    boolean NOT NULL DEFAULT false,
  status         publication_status NOT NULL DEFAULT 'draft',
  reviewed_by    text,
  published_at   timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'published' OR reviewed_by IS NOT NULL)
);

-- Machine-checkable citations for claims in reports and AI answers
CREATE TABLE evidence_links (
  id                 bigserial PRIMARY KEY,
  report_id          bigint REFERENCES analysis_reports(id) ON DELETE CASCADE,
  ai_answer_id       bigint,                            -- FK below
  claim_anchor       text NOT NULL,                     -- paragraph/sentence id
  observation_id     bigint REFERENCES observations(id),
  ranking_version_id bigint REFERENCES ranking_versions(id),
  external_url       text,
  CHECK (num_nonnulls(observation_id, ranking_version_id, external_url) >= 1),
  CHECK (num_nonnulls(report_id, ai_answer_id) = 1)
);

CREATE TABLE report_entities (
  report_id bigint NOT NULL REFERENCES analysis_reports(id) ON DELETE CASCADE,
  entity_id bigint NOT NULL REFERENCES entities(id),
  PRIMARY KEY (report_id, entity_id)
);
CREATE TABLE report_topics (
  report_id bigint NOT NULL REFERENCES analysis_reports(id) ON DELETE CASCADE,
  topic_id  integer NOT NULL REFERENCES topics(id),
  PRIMARY KEY (report_id, topic_id)
);
CREATE TABLE ranking_topics (
  ranking_id bigint NOT NULL REFERENCES rankings(id) ON DELETE CASCADE,
  topic_id   integer NOT NULL REFERENCES topics(id),
  PRIMARY KEY (ranking_id, topic_id)
);

-- ---------------------------------------------------------------------------
-- Users, saved views, plans (built in later phases; modelled now)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
  id           bigserial PRIMARY KEY,
  email        citext UNIQUE NOT NULL,
  display_name text,
  plan         text NOT NULL DEFAULT 'free' CHECK (plan IN ('free','pro','enterprise')),
  created_at   timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE rankings
  ADD CONSTRAINT rankings_owner_fk FOREIGN KEY (owner_user_id) REFERENCES users(id);

CREATE TABLE user_saved_views (
  id          bigserial PRIMARY KEY,
  user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('comparison','ranking_filter','custom_index','chart')),
  title       text NOT NULL,
  config      jsonb NOT NULL,
  is_public   boolean NOT NULL DEFAULT false,
  share_slug  text UNIQUE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
  id           bigserial PRIMARY KEY,
  user_id      bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  key_prefix   text NOT NULL,
  key_hash     text NOT NULL,                           -- never store plaintext
  scopes       text[] NOT NULL DEFAULT '{read}',
  rate_limit_per_min integer NOT NULL DEFAULT 60,
  revoked_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai_answers (
  id            bigserial PRIMARY KEY,
  user_id       bigint REFERENCES users(id),
  question      text NOT NULL,
  answer_md     text NOT NULL,
  tool_calls    jsonb NOT NULL DEFAULT '[]',            -- full trace for audit
  grounded      boolean NOT NULL,                       -- false => answer declined / partial
  model         text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE evidence_links
  ADD CONSTRAINT evidence_links_ai_fk FOREIGN KEY (ai_answer_id) REFERENCES ai_answers(id) ON DELETE CASCADE;

CREATE TABLE data_issue_reports (
  id              bigserial PRIMARY KEY,
  entity_id       bigint REFERENCES entities(id),
  indicator_id    bigint REFERENCES indicators(id),
  observation_id  bigint REFERENCES observations(id),
  page_url        text NOT NULL,
  message         text NOT NULL,
  reporter_email  citext,
  status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open','confirmed','fixed','wontfix')),
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Immutability of published ranking versions
-- ---------------------------------------------------------------------------
CREATE FUNCTION forbid_published_version_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'published' THEN
    -- Only allowed transition: published -> retired
    IF TG_OP = 'UPDATE' AND NEW.status = 'retired'
       AND (to_jsonb(NEW) - 'status') = (to_jsonb(OLD) - 'status') THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'ranking_version % is published and immutable', OLD.id;
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER ranking_versions_immutable
  BEFORE UPDATE OR DELETE ON ranking_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_published_version_change();

CREATE FUNCTION forbid_child_change_if_published() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_status publication_status;
BEGIN
  SELECT status INTO v_status FROM ranking_versions
   WHERE id = COALESCE(NEW.ranking_version_id, OLD.ranking_version_id);
  IF v_status IN ('published','retired') THEN
    RAISE EXCEPTION '% rows of a published ranking_version are immutable', TG_TABLE_NAME;
  END IF;
  RETURN COALESCE(NEW, OLD);
END $$;

CREATE TRIGGER ranking_pillars_immutable    BEFORE INSERT OR UPDATE OR DELETE ON ranking_pillars    FOR EACH ROW EXECUTE FUNCTION forbid_child_change_if_published();
CREATE TRIGGER ranking_indicators_immutable BEFORE INSERT OR UPDATE OR DELETE ON ranking_indicators FOR EACH ROW EXECUTE FUNCTION forbid_child_change_if_published();
CREATE TRIGGER ranking_inputs_immutable     BEFORE INSERT OR UPDATE OR DELETE ON ranking_inputs     FOR EACH ROW EXECUTE FUNCTION forbid_child_change_if_published();
CREATE TRIGGER ranking_results_immutable    BEFORE INSERT OR UPDATE OR DELETE ON ranking_results    FOR EACH ROW EXECUTE FUNCTION forbid_child_change_if_published();
-- Note: the publish job writes results while status='in_review', then flips to 'published'.
