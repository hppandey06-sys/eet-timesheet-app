-- ═══════════════════════════════════════════════════════════
-- EET Fuels Timesheet — Custom Activity Codes Table
-- Run ONE time in Supabase SQL Editor for the new app
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS ts_custom_acts (
  id          BIGINT PRIMARY KEY,
  code        TEXT NOT NULL,
  description TEXT,
  discipline  TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE ts_custom_acts DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_custom_acts_disc ON ts_custom_acts(discipline);

-- Verify
SELECT 'Custom acts table ready' as status;
