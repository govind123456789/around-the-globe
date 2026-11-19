-- D1 schema for optional API keys. Create once:
--   npx wrangler d1 create around-the-globe-api
--   npx wrangler d1 execute around-the-globe-api --remote --file worker/schema.sql
-- then uncomment the d1_databases block in wrangler.jsonc with the database_id it prints.
-- Stored: a SHA-256 hash of each key (never the key), the email it was issued to, the tier and status,
-- and a daily request count per key, or per daily-changing hash of an anonymous IP (no raw IPs, paths or query strings).
CREATE TABLE IF NOT EXISTS api_keys (
  key_hash   TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  tier       TEXT NOT NULL DEFAULT 'free',      -- free | commercial
  status     TEXT NOT NULL DEFAULT 'active',    -- active | revoked
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS api_keys_email ON api_keys (email);

CREATE TABLE IF NOT EXISTS api_usage (
  subject TEXT NOT NULL,                        -- "key:<hash prefix>" or "ip:<daily hash>"
  tier    TEXT NOT NULL,
  day     TEXT NOT NULL,                        -- YYYY-MM-DD (UTC)
  n       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (subject, day)
);
