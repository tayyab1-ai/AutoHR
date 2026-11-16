import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    website = models.CharField(max_length=300, blank=True, null=True)
    industry = models.CharField(max_length=120, blank=True, null=True)
    company_size = models.CharField(max_length=40, blank=True, null=True)
    country = models.CharField(max_length=80, default="Pakistan")
    city = models.CharField(max_length=80, blank=True, null=True)
    office_address = models.CharField(max_length=300, blank=True, null=True)
    linkedin_profile_url = models.CharField(max_length=300, blank=True, null=True)
    linkedin_email = models.EmailField(blank=True, null=True)
    linkedin_password_encrypted = models.TextField(blank=True, null=True)
    indeed_email = models.EmailField(blank=True, null=True)
    indeed_password_encrypted = models.TextField(blank=True, null=True)
    rozee_email = models.EmailField(blank=True, null=True)
    rozee_password_encrypted = models.TextField(blank=True, null=True)
    company_type = models.CharField(max_length=80, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    founded_year = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = "companies"

    def __str__(self):
        return self.name


class User(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    password_hash = models.CharField(max_length=255)
    google_sub = models.CharField(max_length=64, blank=True, null=True, unique=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    job_title = models.CharField(max_length=120, blank=True, null=True)
    first_name = models.CharField(max_length=80, blank=True, null=True)
    last_name = models.CharField(max_length=80, blank=True, null=True)
    work_email = models.EmailField(blank=True, null=True)
    hr_department = models.CharField(max_length=80, blank=True, null=True)
    profile_complete = models.BooleanField(default=False)
    accepted_terms_at = models.DateTimeField(blank=True, null=True)
    accepted_privacy_at = models.DateTimeField(blank=True, null=True)
    role = models.CharField(max_length=32, default="hr_manager")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self):
        return self.full_name


class JobPosting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(Company, on_delete=models.DO_NOTHING, db_column="company_id")
    created_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        db_column="created_by",
        related_name="created_jobs",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        db_column="approved_by",
        related_name="approved_jobs",
        blank=True,
        null=True,
    )

    title = models.CharField(max_length=200)
    department = models.CharField(max_length=120)
    job_category = models.CharField(max_length=80)
    employment_type = models.CharField(max_length=40)
    work_mode = models.CharField(max_length=40)
    urgency_level = models.CharField(max_length=20, default="normal")
    city = models.CharField(max_length=80)
    target_hires = models.IntegerField(default=1)
    job_description = models.TextField()
    posting_date = models.DateField()
    application_deadline = models.DateField()

    min_experience_years = models.IntegerField(default=0)
    max_experience_years = models.IntegerField(blank=True, null=True)
    fresh_graduate_eligible = models.BooleanField(default=False)
    min_education_level = models.CharField(max_length=80)

    required_skills = ArrayField(models.CharField(max_length=120), default=list)
    programming_languages = ArrayField(models.CharField(max_length=120), default=list)
    frameworks = ArrayField(models.CharField(max_length=120), default=list)
    tools = ArrayField(models.CharField(max_length=120), default=list)
    cloud_platforms = ArrayField(models.CharField(max_length=120), default=list)
    technical_knowledge = models.TextField(blank=True, null=True)

    min_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    max_salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=3, default="PKR")
    salary_period = models.CharField(max_length=20, default="per_month")
    salary_negotiable = models.BooleanField(default=False)
    performance_bonus = models.BooleanField(default=False)
    commission_incentives = models.BooleanField(default=False)
    health_insurance = models.BooleanField(default=False)
    paid_leave_policy = models.TextField(blank=True, null=True)
    provident_fund = models.BooleanField(default=False)
    other_benefits = models.TextField(blank=True, null=True)
    relocation_assistance = models.BooleanField(default=False)
    equipment_provided = models.BooleanField(default=False)

    job_post_tone = models.CharField(max_length=60)
    custom_tone_instructions = models.TextField(blank=True, null=True)
    cv_skill_weight = models.IntegerField(default=50)
    cv_experience_weight = models.IntegerField(default=30)
    cv_education_weight = models.IntegerField(default=20)
    cv_min_passing_score = models.IntegerField(default=60)
    shortlist_after_cv_count = models.IntegerField(default=25)
    shortlist_after_interview_count = models.IntegerField(default=10)

    ai_jd_prompt_payload = models.JSONField(blank=True, null=True)
    ai_generated_jd_draft = models.TextField(blank=True, null=True)
    approved_jd_content = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=32, default="draft")
    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "job_postings"


class JobResponsibility(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_posting = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        db_column="job_posting_id",
        related_name="responsibilities",
    )
    kind = models.CharField(max_length=32)
    sort_order = models.IntegerField(default=0)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "job_responsibilities"


class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Candidates are owned by one company; email is unique per company (see migration 004).
    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        db_column="company_id",
        related_name="candidates",
        blank=True,
        null=True,
    )
    email = models.EmailField()
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, blank=True, null=True)
    linkedin_url = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "candidates"

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class Application(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_posting = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        db_column="job_posting_id",
        related_name="applications",
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        db_column="candidate_id",
        related_name="applications",
    )
    source = models.CharField(max_length=32, default="manual_upload")
    source_message_id = models.CharField(max_length=255, blank=True, null=True)
    resume_file_url = models.TextField()
    resume_original_filename = models.CharField(max_length=255)
    resume_mime_type = models.CharField(max_length=100)
    status = models.CharField(max_length=32, default="applied")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "applications"
        unique_together = [["job_posting", "candidate"]]


class ParsedCv(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="parsed_cv",
    )
    raw_text = models.TextField()
    structured_profile = models.JSONField(default=dict)
    extracted_skills = ArrayField(models.CharField(max_length=150), default=list)
    extracted_experience_years = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    highest_degree = models.CharField(max_length=150, blank=True, null=True)
    parsing_model = models.CharField(max_length=100)
    parsed_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "parsed_cvs"


class CvEvaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="cv_evaluation",
    )
    overall_score = models.DecimalField(max_digits=5, decimal_places=2)
    skill_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    experience_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    education_match_score = models.DecimalField(max_digits=5, decimal_places=2)
    match_breakdown = models.JSONField(default=dict)
    ai_summary = models.TextField()
    strengths = ArrayField(models.TextField(), default=list)
    concerns = ArrayField(models.TextField(), default=list)
    is_shortlisted = models.BooleanField(default=False)
    evaluated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "cv_evaluations"


class CandidateInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="invitation",
    )
    magic_token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "candidate_invitations"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at


class InterviewSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="schedules",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    timezone = models.CharField(max_length=50, default="Asia/Karachi")
    room_url = models.TextField(blank=True, null=True)
    is_rescheduled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "interview_schedules"


class InterviewConsent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview_schedule = models.OneToOneField(
        InterviewSchedule,
        on_delete=models.CASCADE,
        db_column="interview_schedule_id",
        related_name="consent",
    )
    consent_recording = models.BooleanField()
    consent_ai_processing = models.BooleanField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    consented_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "interview_consents"


class Interview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="interviews",
    )
    interview_schedule = models.ForeignKey(
        InterviewSchedule,
        on_delete=models.RESTRICT,
        db_column="interview_schedule_id",
        related_name="interviews",
    )
    status = models.CharField(max_length=32, default="pending")
    recording_url = models.TextField(blank=True, null=True)
    recording_file_size_bytes = models.BigIntegerField(blank=True, null=True)
    media_retention_status = models.CharField(max_length=32, default="active")
    media_purged_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "interviews"


class InterviewStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        db_column="interview_id",
        related_name="stages",
    )
    stage_type = models.CharField(max_length=32)
    sequence_order = models.IntegerField()
    status = models.CharField(max_length=32, default="not_started")
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "interview_stages"
        unique_together = [["interview", "sequence_order"]]


class InterviewQuestionAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stage = models.ForeignKey(
        InterviewStage,
        on_delete=models.CASCADE,
        db_column="stage_id",
        related_name="questions_answers",
    )
    question_number = models.IntegerField()
    question_text = models.TextField()
    audio_clip_url = models.TextField(blank=True, null=True)
    transcript_text = models.TextField(blank=True, null=True)
    duration_seconds = models.IntegerField(blank=True, null=True)
    communication_score = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    confidence_score = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    technical_score = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    relevance_score = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    problem_solving_score = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    ai_rationale = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "interview_questions_answers"
        unique_together = [["stage", "question_number"]]


class InterviewEvaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.OneToOneField(
        Interview,
        on_delete=models.CASCADE,
        db_column="interview_id",
        related_name="evaluation",
    )
    communication_avg = models.DecimalField(max_digits=4, decimal_places=2)
    confidence_avg = models.DecimalField(max_digits=4, decimal_places=2)
    technical_avg = models.DecimalField(max_digits=4, decimal_places=2)
    relevance_avg = models.DecimalField(max_digits=4, decimal_places=2)
    problem_solving_avg = models.DecimalField(max_digits=4, decimal_places=2)
    composite_interview_score = models.DecimalField(max_digits=5, decimal_places=2)
    strengths = ArrayField(models.TextField(), default=list)
    weaknesses = ArrayField(models.TextField(), default=list)
    executive_summary = models.TextField()
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "interview_evaluations"


class CandidateFinalRanking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_posting = models.ForeignKey(
        JobPosting,
        on_delete=models.CASCADE,
        db_column="job_posting_id",
        related_name="final_rankings",
    )
    application = models.OneToOneField(
        Application,
        on_delete=models.CASCADE,
        db_column="application_id",
        related_name="final_ranking",
    )
    final_rank = models.IntegerField()
    cv_score = models.DecimalField(max_digits=5, decimal_places=2)
    interview_score = models.DecimalField(max_digits=5, decimal_places=2)
    composite_score = models.DecimalField(max_digits=5, decimal_places=2)
    decision_verdict = models.CharField(max_length=32)
    ai_justification = models.TextField()
    recording_retained = models.BooleanField(default=False)
    hr_override_verdict = models.CharField(max_length=32, blank=True, null=True)
    hr_feedback_notes = models.TextField(blank=True, null=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "candidate_final_rankings"
        unique_together = [["job_posting", "final_rank"]]


class EmailNotification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        Application,
        on_delete=models.SET_NULL,
        db_column="application_id",
        related_name="notifications",
        blank=True,
        null=True,
    )
    recipient_email = models.EmailField()
    notification_type = models.CharField(max_length=64)
    subject = models.CharField(max_length=255)
    body_text = models.TextField()
    status = models.CharField(max_length=32, default="queued")
    external_provider_id = models.CharField(max_length=255, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "email_notifications"


# Django-managed profile & integration tables
from .profile_models import (  # noqa: E402, F401
    IntegrationConnection,
    JobApplicationFormConfig,
    OAuthCredential,
    ProfileSetup,
)
