-- Candidates belong to one company (tenant isolation). Idempotent; one statement per line.
-- 1) Add the owning company column.
ALTER TABLE candidates ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE CASCADE;
-- 2) A candidate who applied to several companies is split into one copy per extra company, and that company's applications are re-pointed to the copy.
DO $$ DECLARE r RECORD; new_id UUID; BEGIN FOR r IN SELECT DISTINCT a.candidate_id, j.company_id FROM applications a JOIN job_postings j ON j.id = a.job_posting_id JOIN candidates c ON c.id = a.candidate_id WHERE c.company_id IS NULL AND j.company_id <> (SELECT j2.company_id FROM applications a2 JOIN job_postings j2 ON j2.id = a2.job_posting_id WHERE a2.candidate_id = a.candidate_id ORDER BY a2.created_at ASC LIMIT 1) LOOP new_id := gen_random_uuid(); INSERT INTO candidates (id, email, full_name, phone, linkedin_url, location, created_at, updated_at, company_id) SELECT new_id, c.email || '#' || new_id::text, c.full_name, c.phone, c.linkedin_url, c.location, c.created_at, c.updated_at, r.company_id FROM candidates c WHERE c.id = r.candidate_id; UPDATE applications a SET candidate_id = new_id FROM job_postings j WHERE j.id = a.job_posting_id AND a.candidate_id = r.candidate_id AND j.company_id = r.company_id; END LOOP; END $$;
-- 3) Remaining candidates take the company of their (single) application history.
UPDATE candidates c SET company_id = sub.company_id FROM (SELECT DISTINCT ON (a.candidate_id) a.candidate_id, j.company_id FROM applications a JOIN job_postings j ON j.id = a.job_posting_id ORDER BY a.candidate_id, a.created_at ASC) sub WHERE sub.candidate_id = c.id AND c.company_id IS NULL;
-- 4) Email is unique per company instead of globally.
ALTER TABLE candidates DROP CONSTRAINT IF EXISTS uq_candidates_email;
UPDATE candidates SET email = split_part(email, '#', 1) WHERE email LIKE '%#%' AND company_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_candidates_company_email ON candidates (company_id, email);
CREATE INDEX IF NOT EXISTS idx_candidates_company ON candidates (company_id);
