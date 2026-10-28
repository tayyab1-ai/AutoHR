-- AutoHR-N PostgreSQL schema
-- Based on C:\Users\A\Downloads\AutoHR, with the structural fixes described in db_architecture.md.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------

CREATE TYPE user_role_enum AS ENUM ('admin', 'hr_manager', 'interviewer');

CREATE TYPE job_status_enum AS ENUM (
    'draft',
    'pending_approval',
    'approved',
    'published',
    'paused',
    'closed'
);

CREATE TYPE job_board_platform_enum AS ENUM (
    'indeed',
    'rozee_pk',
    'linkedin',
    'custom_career_page'
);

CREATE TYPE board_sync_status_enum AS ENUM (
    'pending',
    'published',
    'failed',
    'expired'
);

CREATE TYPE application_source_enum AS ENUM (
    'email_inbound',
    'web_form',
    'indeed',
    'rozee_pk',
    'manual_upload'
);

CREATE TYPE application_status_enum AS ENUM (
    'applied',
    'parsing_cv',
    'screened',
    'shortlisted',
    'rejected',
    'interview_invited',
    'interview_scheduled',
    'interview_in_progress',
    'interview_completed',
    'final_review',
    'hired',
    'archived'
);

CREATE TYPE interview_stage_type_enum AS ENUM (
    'screening',
    'technical',
    'behavioral'
);

CREATE TYPE stage_status_enum AS ENUM (
    'not_started',
    'in_progress',
    'completed',
    'skipped'
);

CREATE TYPE interview_status_enum AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'cancelled',
    'no_show'
);

CREATE TYPE media_retention_enum AS ENUM (
    'active',
    'marked_for_deletion',
    'purged'
);

CREATE TYPE decision_verdict_enum AS ENUM (
    'strong_hire',
    'hire',
    'lean_hire',
    'no_hire'
);

CREATE TYPE notification_type_enum AS ENUM (
    'rejection',
    'interview_invite',
    'interview_reminder',
    'hr_status_update'
);

CREATE TYPE notification_status_enum AS ENUM (
    'queued',
    'sent',
    'failed'
);

-- ---------------------------------------------------------------------------
-- updated_at
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

-- ---------------------------------------------------------------------------
-- companies
-- One row per employer. Job-board secrets live here once, encrypted by the app.
-- ---------------------------------------------------------------------------

CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    website VARCHAR(300),
    industry VARCHAR(120),
    company_size VARCHAR(40),
    country VARCHAR(80) NOT NULL DEFAULT 'Pakistan',
    city VARCHAR(80),
    office_address VARCHAR(300),
    linkedin_profile_url VARCHAR(300),
    linkedin_email CITEXT,
    linkedin_password_encrypted TEXT,
    indeed_email CITEXT,
    indeed_password_encrypted TEXT,
    rozee_email CITEXT,
    rozee_password_encrypted TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    email CITEXT NOT NULL,
    full_name VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(30),
    job_title VARCHAR(120),
    role user_role_enum NOT NULL DEFAULT 'hr_manager',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX idx_users_company_id ON users (company_id);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- job_postings
-- ---------------------------------------------------------------------------

CREATE TABLE job_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id) ON DELETE RESTRICT,
    created_by UUID NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES users (id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    department VARCHAR(120),
    city VARCHAR(80),
    min_experience_years INT NOT NULL DEFAULT 0,
    max_experience_years INT,
    min_salary NUMERIC(12, 2),
    max_salary NUMERIC(12, 2),
    currency CHAR(3) NOT NULL DEFAULT 'PKR',
    target_hires INT NOT NULL DEFAULT 1,
    shortlist_multiplier NUMERIC(4, 2) NOT NULL DEFAULT 3.0,
    required_skills TEXT[] NOT NULL DEFAULT '{}',
    bonus_skills TEXT[] NOT NULL DEFAULT '{}',
    ai_jd_prompt_payload JSONB,
    ai_generated_jd_draft TEXT,
    approved_jd_content TEXT,
    status job_status_enum NOT NULL DEFAULT 'draft',
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_job_min_experience CHECK (min_experience_years >= 0),
    CONSTRAINT ck_job_max_experience CHECK (
        max_experience_years IS NULL OR max_experience_years >= min_experience_years
    ),
    CONSTRAINT ck_job_min_salary CHECK (min_salary IS NULL OR min_salary >= 0),
    CONSTRAINT ck_job_salary_range CHECK (
        max_salary IS NULL OR min_salary IS NULL OR max_salary >= min_salary
    ),
    CONSTRAINT ck_job_target_hires CHECK (target_hires > 0),
    CONSTRAINT ck_job_shortlist_multiplier CHECK (shortlist_multiplier >= 1.0)
);

CREATE INDEX idx_job_postings_company_id ON job_postings (company_id);
CREATE INDEX idx_job_postings_status ON job_postings (status);
CREATE INDEX idx_job_postings_city ON job_postings (city);
CREATE INDEX idx_job_postings_req_skills_gin ON job_postings USING GIN (required_skills);

CREATE TRIGGER trg_job_postings_updated_at
    BEFORE UPDATE ON job_postings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE FUNCTION enforce_job_company()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    creator_company UUID;
    approver_company UUID;
BEGIN
    SELECT company_id INTO creator_company FROM users WHERE id = NEW.created_by;
    IF creator_company IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'job_postings.company_id must match the creating user''s company';
    END IF;

    IF NEW.approved_by IS NOT NULL THEN
        SELECT company_id INTO approver_company FROM users WHERE id = NEW.approved_by;
        IF approver_company IS DISTINCT FROM NEW.company_id THEN
            RAISE EXCEPTION 'job_postings.approved_by must belong to the same company';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_job_postings_company
    BEFORE INSERT OR UPDATE ON job_postings
    FOR EACH ROW EXECUTE FUNCTION enforce_job_company();

-- ---------------------------------------------------------------------------
-- job_board_postings
-- ---------------------------------------------------------------------------

CREATE TABLE job_board_postings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
    platform job_board_platform_enum NOT NULL,
    external_job_id VARCHAR(255),
    post_url TEXT,
    sync_status board_sync_status_enum NOT NULL DEFAULT 'pending',
    response_payload JSONB,
    error_message TEXT,
    published_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_platform UNIQUE (job_posting_id, platform)
);

CREATE INDEX idx_job_board_postings_status
    ON job_board_postings (job_posting_id, platform, sync_status);

CREATE TRIGGER trg_job_board_postings_updated_at
    BEFORE UPDATE ON job_board_postings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- candidates and applications
-- ---------------------------------------------------------------------------

CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    phone VARCHAR(50),
    linkedin_url TEXT,
    location VARCHAR(150),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_candidates_email UNIQUE (email)
);

CREATE INDEX idx_candidates_email ON candidates (email);

CREATE TRIGGER trg_candidates_updated_at
    BEFORE UPDATE ON candidates
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates (id) ON DELETE CASCADE,
    source application_source_enum NOT NULL DEFAULT 'web_form',
    source_message_id VARCHAR(255),
    resume_file_url TEXT NOT NULL,
    resume_original_filename VARCHAR(255) NOT NULL,
    resume_mime_type VARCHAR(100) NOT NULL,
    status application_status_enum NOT NULL DEFAULT 'applied',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_candidate UNIQUE (job_posting_id, candidate_id)
);

CREATE INDEX idx_applications_job_id_status ON applications (job_posting_id, status);
CREATE INDEX idx_applications_candidate_id ON applications (candidate_id);

CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON applications
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE parsed_cvs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    raw_text TEXT NOT NULL,
    structured_profile JSONB NOT NULL,
    extracted_skills TEXT[] NOT NULL DEFAULT '{}',
    extracted_experience_years NUMERIC(4, 1),
    highest_degree VARCHAR(150),
    parsing_model VARCHAR(100) NOT NULL,
    parsed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_parsed_experience CHECK (
        extracted_experience_years IS NULL OR extracted_experience_years >= 0
    )
);

CREATE INDEX idx_parsed_cvs_profile_gin ON parsed_cvs USING GIN (structured_profile);
CREATE INDEX idx_parsed_cvs_skills_gin ON parsed_cvs USING GIN (extracted_skills);

CREATE TABLE cv_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    overall_score NUMERIC(5, 2) NOT NULL,
    skill_match_score NUMERIC(5, 2) NOT NULL,
    experience_match_score NUMERIC(5, 2) NOT NULL,
    education_match_score NUMERIC(5, 2) NOT NULL,
    match_breakdown JSONB NOT NULL DEFAULT '{}',
    ai_summary TEXT NOT NULL,
    strengths TEXT[] NOT NULL DEFAULT '{}',
    concerns TEXT[] NOT NULL DEFAULT '{}',
    is_shortlisted BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_cv_overall CHECK (overall_score BETWEEN 0 AND 100),
    CONSTRAINT ck_cv_skill CHECK (skill_match_score BETWEEN 0 AND 100),
    CONSTRAINT ck_cv_experience CHECK (experience_match_score BETWEEN 0 AND 100),
    CONSTRAINT ck_cv_education CHECK (education_match_score BETWEEN 0 AND 100)
);

CREATE INDEX idx_cv_evaluations_overall_score ON cv_evaluations (overall_score DESC);
CREATE INDEX idx_cv_evaluations_shortlisted ON cv_evaluations (is_shortlisted);

CREATE TABLE candidate_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    magic_token VARCHAR(128) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_used BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMPTZ,
    CONSTRAINT uq_invitation_token UNIQUE (magic_token)
);

CREATE INDEX idx_candidate_invitations_token ON candidate_invitations (magic_token);

-- ---------------------------------------------------------------------------
-- interviews
-- ---------------------------------------------------------------------------

CREATE TABLE interview_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Karachi',
    room_url TEXT,
    is_rescheduled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_schedule_window CHECK (scheduled_end > scheduled_start)
);

CREATE TABLE interview_consents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_schedule_id UUID NOT NULL UNIQUE REFERENCES interview_schedules (id) ON DELETE CASCADE,
    consent_recording BOOLEAN NOT NULL,
    consent_ai_processing BOOLEAN NOT NULL,
    ip_address INET NOT NULL,
    user_agent TEXT NOT NULL,
    consented_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    interview_schedule_id UUID NOT NULL REFERENCES interview_schedules (id) ON DELETE RESTRICT,
    status interview_status_enum NOT NULL DEFAULT 'pending',
    recording_url TEXT,
    recording_file_size_bytes BIGINT,
    media_retention_status media_retention_enum NOT NULL DEFAULT 'active',
    media_purged_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_interview_window CHECK (
        ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at
    ),
    CONSTRAINT ck_recording_size CHECK (
        recording_file_size_bytes IS NULL OR recording_file_size_bytes >= 0
    )
);

CREATE INDEX idx_interviews_retention
    ON interviews (media_retention_status)
    WHERE media_retention_status = 'active';

CREATE TABLE interview_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews (id) ON DELETE CASCADE,
    stage_type interview_stage_type_enum NOT NULL,
    sequence_order INT NOT NULL,
    status stage_status_enum NOT NULL DEFAULT 'not_started',
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    CONSTRAINT uq_interview_stage_order UNIQUE (interview_id, sequence_order),
    CONSTRAINT uq_interview_stage_type UNIQUE (interview_id, stage_type),
    CONSTRAINT ck_stage_sequence CHECK (sequence_order IN (1, 2, 3))
);

CREATE TABLE interview_questions_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id UUID NOT NULL REFERENCES interview_stages (id) ON DELETE CASCADE,
    question_number INT NOT NULL,
    question_text TEXT NOT NULL,
    audio_clip_url TEXT,
    transcript_text TEXT,
    duration_seconds INT,
    communication_score NUMERIC(4, 2),
    confidence_score NUMERIC(4, 2),
    technical_score NUMERIC(4, 2),
    relevance_score NUMERIC(4, 2),
    problem_solving_score NUMERIC(4, 2),
    ai_rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_stage_question_number UNIQUE (stage_id, question_number),
    CONSTRAINT ck_question_number CHECK (question_number > 0),
    CONSTRAINT ck_duration_seconds CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    CONSTRAINT ck_communication_score CHECK (communication_score IS NULL OR communication_score BETWEEN 0 AND 10),
    CONSTRAINT ck_confidence_score CHECK (confidence_score IS NULL OR confidence_score BETWEEN 0 AND 10),
    CONSTRAINT ck_technical_score CHECK (technical_score IS NULL OR technical_score BETWEEN 0 AND 10),
    CONSTRAINT ck_relevance_score CHECK (relevance_score IS NULL OR relevance_score BETWEEN 0 AND 10),
    CONSTRAINT ck_problem_solving_score CHECK (problem_solving_score IS NULL OR problem_solving_score BETWEEN 0 AND 10)
);

CREATE TABLE interview_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL UNIQUE REFERENCES interviews (id) ON DELETE CASCADE,
    communication_avg NUMERIC(4, 2) NOT NULL,
    confidence_avg NUMERIC(4, 2) NOT NULL,
    technical_avg NUMERIC(4, 2) NOT NULL,
    relevance_avg NUMERIC(4, 2) NOT NULL,
    problem_solving_avg NUMERIC(4, 2) NOT NULL,
    composite_interview_score NUMERIC(5, 2) NOT NULL,
    strengths TEXT[] NOT NULL DEFAULT '{}',
    weaknesses TEXT[] NOT NULL DEFAULT '{}',
    executive_summary TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_eval_communication CHECK (communication_avg BETWEEN 0 AND 10),
    CONSTRAINT ck_eval_confidence CHECK (confidence_avg BETWEEN 0 AND 10),
    CONSTRAINT ck_eval_technical CHECK (technical_avg BETWEEN 0 AND 10),
    CONSTRAINT ck_eval_relevance CHECK (relevance_avg BETWEEN 0 AND 10),
    CONSTRAINT ck_eval_problem_solving CHECK (problem_solving_avg BETWEEN 0 AND 10),
    CONSTRAINT ck_eval_composite CHECK (composite_interview_score BETWEEN 0 AND 100)
);

-- ---------------------------------------------------------------------------
-- rankings and mail
-- ---------------------------------------------------------------------------

CREATE TABLE candidate_final_rankings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_posting_id UUID NOT NULL REFERENCES job_postings (id) ON DELETE CASCADE,
    application_id UUID NOT NULL UNIQUE REFERENCES applications (id) ON DELETE CASCADE,
    final_rank INT NOT NULL,
    cv_score NUMERIC(5, 2) NOT NULL,
    interview_score NUMERIC(5, 2) NOT NULL,
    composite_score NUMERIC(5, 2) NOT NULL,
    decision_verdict decision_verdict_enum NOT NULL,
    ai_justification TEXT NOT NULL,
    recording_retained BOOLEAN NOT NULL DEFAULT FALSE,
    hr_override_verdict decision_verdict_enum,
    hr_feedback_notes TEXT,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_rank UNIQUE (job_posting_id, final_rank),
    CONSTRAINT ck_final_rank CHECK (final_rank > 0),
    CONSTRAINT ck_rank_cv CHECK (cv_score BETWEEN 0 AND 100),
    CONSTRAINT ck_rank_interview CHECK (interview_score BETWEEN 0 AND 100),
    CONSTRAINT ck_rank_composite CHECK (composite_score BETWEEN 0 AND 100)
);

CREATE INDEX idx_final_rankings_leaderboard
    ON candidate_final_rankings (job_posting_id, final_rank ASC);
CREATE INDEX idx_final_rankings_score
    ON candidate_final_rankings (job_posting_id, composite_score DESC);

CREATE OR REPLACE FUNCTION enforce_ranking_job()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    application_job UUID;
BEGIN
    SELECT job_posting_id INTO application_job
    FROM applications
    WHERE id = NEW.application_id;

    IF application_job IS DISTINCT FROM NEW.job_posting_id THEN
        RAISE EXCEPTION 'candidate_final_rankings.job_posting_id must match the application job';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_rankings_job
    BEFORE INSERT OR UPDATE ON candidate_final_rankings
    FOR EACH ROW EXECUTE FUNCTION enforce_ranking_job();

CREATE TABLE email_notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications (id) ON DELETE SET NULL,
    recipient_email CITEXT NOT NULL,
    notification_type notification_type_enum NOT NULL,
    subject VARCHAR(255) NOT NULL,
    body_text TEXT NOT NULL,
    status notification_status_enum NOT NULL DEFAULT 'queued',
    external_provider_id VARCHAR(255),
    error_message TEXT,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_notifications_recipient ON email_notifications (recipient_email);
CREATE INDEX idx_email_notifications_application ON email_notifications (application_id);
