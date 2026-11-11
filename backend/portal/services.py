import re

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from .choices import DEPARTMENTS, JOB_CATEGORIES
from .groq_jd import generate_job_description_text
from .models import Application, JobPosting, JobResponsibility

_DEPT_LABELS = dict(DEPARTMENTS)
_CATEGORY_LABELS = dict(JOB_CATEGORIES)


@transaction.atomic
def create_job_posting(company, user, cleaned_data) -> JobPosting:
    now = timezone.now()
    job = JobPosting.objects.create(
        company=company,
        created_by=user,
        title=cleaned_data["title"].strip(),
        department=cleaned_data["department"],
        job_category=cleaned_data["job_category"],
        employment_type=cleaned_data["employment_type"],
        work_mode=cleaned_data["work_mode"],
        urgency_level=cleaned_data["urgency_level"],
        city=cleaned_data["city"],
        target_hires=cleaned_data["target_hires"],
        job_description=cleaned_data["job_description"].strip(),
        posting_date=cleaned_data["posting_date"],
        application_deadline=cleaned_data["application_deadline"],
        min_experience_years=cleaned_data["min_experience_years"],
        max_experience_years=cleaned_data.get("max_experience_years"),
        fresh_graduate_eligible=cleaned_data["fresh_graduate_eligible_bool"],
        min_education_level=cleaned_data["min_education_level"],
        required_skills=cleaned_data["required_skills_list"],
        programming_languages=cleaned_data["programming_languages_list"],
        frameworks=cleaned_data["frameworks_list"],
        tools=cleaned_data["tools_list"],
        cloud_platforms=cleaned_data["cloud_platforms_list"],
        technical_knowledge=(cleaned_data.get("technical_knowledge") or "").strip() or None,
        min_salary=cleaned_data.get("min_salary"),
        max_salary=cleaned_data.get("max_salary"),
        currency="PKR",
        salary_period=cleaned_data["salary_period"],
        salary_negotiable=bool(cleaned_data.get("salary_negotiable")),
        performance_bonus=bool(cleaned_data.get("performance_bonus")),
        commission_incentives=bool(cleaned_data.get("commission_incentives")),
        health_insurance=bool(cleaned_data.get("health_insurance")),
        paid_leave_policy=(cleaned_data.get("paid_leave_policy") or "").strip() or None,
        provident_fund=bool(cleaned_data.get("provident_fund")),
        other_benefits=(cleaned_data.get("other_benefits") or "").strip() or None,
        relocation_assistance=bool(cleaned_data.get("relocation_assistance")),
        equipment_provided=bool(cleaned_data.get("equipment_provided")),
        job_post_tone=cleaned_data["job_post_tone"],
        custom_tone_instructions=(cleaned_data.get("custom_tone_instructions") or "").strip() or None,
        cv_skill_weight=cleaned_data["cv_skill_weight"],
        cv_experience_weight=cleaned_data["cv_experience_weight"],
        cv_education_weight=cleaned_data["cv_education_weight"],
        cv_min_passing_score=cleaned_data["cv_min_passing_score"],
        shortlist_after_cv_count=cleaned_data["shortlist_after_cv_count"],
        shortlist_after_interview_count=cleaned_data["shortlist_after_interview_count"],
        ai_jd_prompt_payload={
            "intake_snapshot": {
                "title": cleaned_data["title"],
                "tone": cleaned_data["job_post_tone"],
                "required_skills": cleaned_data["required_skills_list"],
                "cv_scoring_metrics": {
                    "skill_weight": cleaned_data["cv_skill_weight"],
                    "experience_weight": cleaned_data["cv_experience_weight"],
                    "education_weight": cleaned_data["cv_education_weight"],
                    "min_passing_score": cleaned_data["cv_min_passing_score"],
                },
            }
        },
        status="draft",
        created_at=now,
        updated_at=now,
    )

    for order, body in enumerate(cleaned_data["key_responsibilities_list"]):
        JobResponsibility.objects.create(
            job_posting=job,
            kind="key_responsibility",
            sort_order=order,
            body=body,
        )
    for order, body in enumerate(cleaned_data["daily_tasks_list"]):
        JobResponsibility.objects.create(
            job_posting=job,
            kind="daily_task",
            sort_order=order,
            body=body,
        )
    return job


def jobs_for_dashboard(company):
    app_counts = {
        row["job_posting_id"]: row["total"]
        for row in Application.objects.filter(job_posting__company=company)
        .values("job_posting_id")
        .annotate(total=Count("id"))
    }
    rows = []
    for job in JobPosting.objects.filter(company=company).order_by("-created_at")[:50]:
        salary = "Not disclosed"
        if job.min_salary is not None:
            lo = f"{int(job.min_salary):,}"
            hi = f"{int(job.max_salary):,}" if job.max_salary else None
            period = job.salary_period.replace("per_", "").replace("_", " ")
            salary = f"PKR {lo}" + (f" – {hi}" if hi else "+") + f" / {period}"

        status = "draft"
        if job.status == "published":
            status = "live"
        elif job.status == "approved":
            status = "approved"
        elif job.status == "closed":
            status = "closed"

        has_jd = bool((job.ai_generated_jd_draft or "").strip())
        rows.append(
            {
                "id": str(job.id),
                "title": job.title,
                "department": _DEPT_LABELS.get(job.department, job.department),
                "city": job.city,
                "salary": salary,
                "hires": job.target_hires,
                "applicants": app_counts.get(job.id, 0),
                "status": status,
                "posted": job.posting_date.strftime("%d %b %Y"),
                "boards": [],
                "is_draft": job.status == "draft",
                "has_jd": has_jd,
                "can_publish": has_jd and not (job.approved_jd_content or "").strip(),
                "cv_skill_weight": job.cv_skill_weight,
                "cv_experience_weight": job.cv_experience_weight,
                "cv_education_weight": job.cv_education_weight,
                "cv_min_passing_score": job.cv_min_passing_score,
                "shortlist_after_cv_count": job.shortlist_after_cv_count,
                "required_skills": job.required_skills or [],
                "min_experience_years": job.min_experience_years,
                "min_education_level": job.min_education_level,
            }
        )
    return rows


@transaction.atomic
def update_job_cv_metrics(
    job: JobPosting,
    *,
    skill_weight: int,
    experience_weight: int,
    education_weight: int,
    min_passing_score: int,
    shortlist_after_cv_count: int | None = None,
) -> tuple[JobPosting, int]:
    """Validate and save CV metric weights on a job, then recalculate existing CV evaluations."""
    for label, val in (
        ("Skills weight", skill_weight),
        ("Experience weight", experience_weight),
        ("Education weight", education_weight),
        ("Minimum passing score", min_passing_score),
    ):
        if not (0 <= val <= 100):
            raise ValueError(f"{label} must be between 0 and 100.")
    if skill_weight + experience_weight + education_weight != 100:
        raise ValueError("Skills, Experience, and Education weights must total 100%.")

    update_fields = [
        "cv_skill_weight",
        "cv_experience_weight",
        "cv_education_weight",
        "cv_min_passing_score",
        "updated_at",
    ]
    job.cv_skill_weight = skill_weight
    job.cv_experience_weight = experience_weight
    job.cv_education_weight = education_weight
    job.cv_min_passing_score = min_passing_score

    if shortlist_after_cv_count is not None:
        if not (20 <= shortlist_after_cv_count <= 30):
            raise ValueError("Shortlist cap must be between 20 and 30.")
        job.shortlist_after_cv_count = shortlist_after_cv_count
        update_fields.append("shortlist_after_cv_count")

    job.updated_at = timezone.now()
    job.save(update_fields=update_fields)

    from .cv_scoring_service import recalculate_job_cv_scores

    updated_count = recalculate_job_cv_scores(job)
    return job, updated_count


def draft_jobs_for_user(company, user):
    return [
        j
        for j in JobPosting.objects.filter(company=company, created_by=user, status="draft").order_by(
            "-updated_at"
        )[:30]
    ]


def get_job_for_company(job_id, company) -> JobPosting:
    return (
        JobPosting.objects.select_related("company")
        .prefetch_related("responsibilities")
        .get(id=job_id, company=company)
    )


def generate_ai_job_description(job: JobPosting) -> JobPosting:
    text, meta = generate_job_description_text(job)
    now = timezone.now()
    payload = job.ai_jd_prompt_payload or {}
    if not isinstance(payload, dict):
        payload = {}
    payload["last_generation"] = meta
    job.ai_generated_jd_draft = text
    job.ai_jd_prompt_payload = payload
    job.updated_at = now
    job.save(update_fields=["ai_generated_jd_draft", "ai_jd_prompt_payload", "updated_at"])
    return job


def save_finalized_job_description(job: JobPosting, content: str) -> JobPosting:
    """Persist HR-approved copy (edited or same as AI draft)."""
    now = timezone.now()
    job.approved_jd_content = content.strip()
    job.updated_at = now
    job.save(update_fields=["approved_jd_content", "updated_at"])
    return job


def inject_apply_link_into_job_description(job: JobPosting, form_url: str) -> JobPosting:
    """Insert Google Form URL after Apply Here: in the finalized description."""
    url = (form_url or "").strip()
    if not url:
        raise ValueError("Form URL is required.")
    content = (job.approved_jd_content or job.ai_generated_jd_draft or "").strip()
    if re.search(r"Apply Here:\s*\S+", content, re.MULTILINE | re.IGNORECASE):
        content = re.sub(
            r"(Apply Here:\s*)(\S[^\n]*)",
            rf"\1{url}",
            content,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    elif re.search(r"Apply Here:\s*$", content, re.MULTILINE | re.IGNORECASE):
        content = re.sub(
            r"(Apply Here:\s*)$",
            rf"\1{url}",
            content,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    else:
        if "How to Apply" not in content:
            content += "\n\nHow to Apply"
        content += f"\nApply Here: {url}"
    job.status = "approved"
    return save_finalized_job_description(job, content)


def save_job_description_draft(job: JobPosting, content: str) -> JobPosting:
    """Keep edited JD on a draft job (e.g. before profile setup is complete)."""
    now = timezone.now()
    job.ai_generated_jd_draft = content.strip()
    job.status = "draft"
    job.updated_at = now
    job.save(update_fields=["ai_generated_jd_draft", "status", "updated_at"])
    return job
