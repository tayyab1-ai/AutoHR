-- Per-job CV scoring metric weights and minimum passing threshold
ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS cv_skill_weight INT NOT NULL DEFAULT 50;
ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS cv_experience_weight INT NOT NULL DEFAULT 30;
ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS cv_education_weight INT NOT NULL DEFAULT 20;
ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS cv_min_passing_score INT NOT NULL DEFAULT 60;
ALTER TABLE job_postings DROP CONSTRAINT IF EXISTS ck_job_cv_weights_sum;
ALTER TABLE job_postings ADD CONSTRAINT ck_job_cv_weights_sum CHECK (cv_skill_weight >= 0 AND cv_experience_weight >= 0 AND cv_education_weight >= 0 AND cv_skill_weight + cv_experience_weight + cv_education_weight = 100);
ALTER TABLE job_postings DROP CONSTRAINT IF EXISTS ck_job_cv_min_passing;
ALTER TABLE job_postings ADD CONSTRAINT ck_job_cv_min_passing CHECK (cv_min_passing_score BETWEEN 0 AND 100);

