-- ============================================================
-- RemotePulse — Supabase Database Setup
-- Run this ONCE in the Supabase SQL Editor
-- ============================================================

-- 1. Create jobs table
CREATE TABLE IF NOT EXISTS jobs (
  id          BIGSERIAL PRIMARY KEY,
  title       TEXT NOT NULL,
  company     TEXT,
  location    TEXT DEFAULT 'Worldwide',
  site        TEXT,
  salary      TEXT,
  job_type    TEXT,
  url         TEXT UNIQUE NOT NULL,   -- unique prevents duplicates
  date_posted DATE,
  description TEXT,
  search_term TEXT,
  fetched_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create saved_jobs table (for your bookmarks)
CREATE TABLE IF NOT EXISTS saved_jobs (
  id         BIGSERIAL PRIMARY KEY,
  job_url    TEXT NOT NULL UNIQUE,
  saved_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create applied_jobs table (track your applications)
CREATE TABLE IF NOT EXISTS applied_jobs (
  id          BIGSERIAL PRIMARY KEY,
  job_url     TEXT NOT NULL UNIQUE,
  job_title   TEXT,
  company     TEXT,
  applied_at  TIMESTAMPTZ DEFAULT NOW(),
  status      TEXT DEFAULT 'Applied',   -- Applied, Interview, Rejected, Offer
  notes       TEXT
);

-- 4. Enable Row Level Security (keep data private)
ALTER TABLE jobs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_jobs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE applied_jobs ENABLE ROW LEVEL SECURITY;

-- 5. Allow public read on jobs (your dashboard needs this)
CREATE POLICY "Public read jobs"
  ON jobs FOR SELECT
  USING (true);

-- 6. Allow insert/upsert on jobs (GitHub Actions needs this)
CREATE POLICY "Public insert jobs"
  ON jobs FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Public update jobs"
  ON jobs FOR UPDATE
  USING (true);

-- 7. Allow full access to saved/applied (your dashboard manages these)
CREATE POLICY "Public access saved_jobs"
  ON saved_jobs FOR ALL
  USING (true);

CREATE POLICY "Public access applied_jobs"
  ON applied_jobs FOR ALL
  USING (true);

-- 8. Auto-delete jobs older than 7 days (keeps DB clean)
-- Run this manually or set up as a Supabase cron (pg_cron)
-- DELETE FROM jobs WHERE fetched_at < NOW() - INTERVAL '7 days';

-- 9. Index for faster queries
CREATE INDEX IF NOT EXISTS idx_jobs_fetched ON jobs(fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_site    ON jobs(site);
CREATE INDEX IF NOT EXISTS idx_jobs_date    ON jobs(date_posted DESC);

-- Done! Check your tables in Table Editor →
SELECT COUNT(*) as total_jobs FROM jobs;
