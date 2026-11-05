-- Profile wizard & integrations (run once on autohr_n)
-- psql -U autohr -d autohr_n -f database/migrations/001_profile_integrations.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(80);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(80);
ALTER TABLE users ADD COLUMN IF NOT EXISTS work_email CITEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS hr_department VARCHAR(80);
ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_complete BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_terms_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS accepted_privacy_at TIMESTAMPTZ;

ALTER TABLE companies ADD COLUMN IF NOT EXISTS company_type VARCHAR(80);
ALTER TABLE companies ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE companies ADD COLUMN IF NOT EXISTS founded_year INT;
