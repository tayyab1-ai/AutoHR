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


# Django-managed profile & integration tables
from .profile_models import IntegrationConnection, OAuthCredential, ProfileSetup  # noqa: E402, F401
