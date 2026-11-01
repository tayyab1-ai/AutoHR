from django.db import transaction
from django.utils import timezone

from .choices import DEPARTMENTS, JOB_CATEGORIES
from .models import JobPosting, JobResponsibility

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
        shortlist_after_cv_count=cleaned_data["shortlist_after_cv_count"],
        shortlist_after_interview_count=cleaned_data["shortlist_after_interview_count"],
        ai_jd_prompt_payload={
            "intake_snapshot": {
                "title": cleaned_data["title"],
                "tone": cleaned_data["job_post_tone"],
                "required_skills": cleaned_data["required_skills_list"],
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
        elif job.status == "closed":
            status = "closed"

        rows.append(
            {
                "title": job.title,
                "department": _DEPT_LABELS.get(job.department, job.department),
                "city": job.city,
                "salary": salary,
                "hires": job.target_hires,
                "applicants": 0,
                "status": status,
                "posted": job.posting_date.strftime("%d %b %Y"),
                "boards": [],
            }
        )
    return rows
