"""Helpers for the signed-in HR user and company."""


from django.utils.html import escape

from .cv_scoring_service import applications_for_company
from .models import InterviewSchedule


def build_hr_profile(db_user, company) -> dict:
    parts = (db_user.full_name or "").split()
    initials = "".join(p[0].upper() for p in parts[:2] if p) or "HR"
    first = getattr(db_user, "first_name", None) or (parts[0] if parts else "")
    last = getattr(db_user, "last_name", None) or (" ".join(parts[1:]) if len(parts) > 1 else "")
    work_email = getattr(db_user, "work_email", None)
    return {
        "full_name": db_user.full_name,
        "first_name": first or "",
        "last_name": last or "",
        "job_title": db_user.job_title or "HR",
        "email": db_user.email,
        "work_email": work_email or "—",
        "hr_department": getattr(db_user, "hr_department", None) or "—",
        "phone": db_user.phone or "—",
        "profile_complete": bool(getattr(db_user, "profile_complete", False)),
        "company_name": company.name,
        "company_website": company.website or "—",
        "industry": company.industry or "—",
        "company_size": company.company_size or "—",
        "country": company.country or "Pakistan",
        "city": company.city or "—",
        "office_address": company.office_address or "—",
        "linkedin_profile_url": company.linkedin_profile_url or "—",
        "linkedin_email": company.linkedin_email or "—",
        "indeed_email": company.indeed_email or "—",
        "rozee_email": company.rozee_email or "—",
        "initials": initials,
    }


def workspace_shell(*, active_jobs: int = 0) -> dict:
    """Empty dashboard panels until applications/pipeline/reports are wired to the DB."""
    return {
        "kpis": [
            {
                "label": "Active Job Postings",
                "value": str(active_jobs),
                "trend": "From your workspace",
                "icon": "bi-briefcase-fill",
                "tone": "gold",
                "hint": "Jobs you create appear here and in the Jobs tab.",
            },
            {
                "label": "Applications Received",
                "value": "0",
                "trend": "Not connected yet",
                "icon": "bi-people-fill",
                "tone": "green",
                "hint": "Candidate applications will show here in a later release.",
            },
            {
                "label": "AI Shortlisted",
                "value": "0",
                "trend": "—",
                "icon": "bi-stars",
                "tone": "purple",
                "hint": "AI screening metrics will appear when applications are live.",
            },
            {
                "label": "Interviews Scheduled",
                "value": "0",
                "trend": "—",
                "icon": "bi-camera-video-fill",
                "tone": "teal",
                "hint": "Interview scheduling will appear in a later release.",
            },
        ],
        "funnel": [],
        "activity": [],
        "candidates": [],
        "interviews": [],
        "kanban": [],
        "reports": {
            "time_to_hire": "—",
            "cost_per_hire": "—",
            "offer_acceptance": "—",
            "top_source": "—",
        },
        "chart_months": ["—", "—", "—", "—", "—", "—"],
        "chart_values": [0, 0, 0, 0, 0, 0],
        "chart_max": 1,
    }


def workspace_shell_for_company(company, *, jobs: list[dict]) -> dict:
    """Build real dashboard KPIs, CV candidate scorecards, funnel, and Kanban pipeline."""
    active_jobs = len([j for j in jobs if j.get("status") != "draft"])
    candidates = applications_for_company(company)
    total_apps = len(candidates)
    shortlisted = [c for c in candidates if c["status"] == "shortlisted"]
    interview_statuses = {
        "interviewing",
        "interview_invited",
        "interview_scheduled",
        "interview_in_progress",
        "interview_completed",
        "final_review",
    }
    interviewing = [c for c in candidates if c["status"] in interview_statuses]
    rejected = [c for c in candidates if c["status"] == "rejected"]
    screened = [c for c in candidates if c["status"] == "screened"]

    avg_score = round(sum(c["overall_score"] for c in candidates) / total_apps, 1) if total_apps else None
    shortlisted_count = len(shortlisted)
    interview_count = len(interviewing)

    shell = workspace_shell(active_jobs=active_jobs)
    shell["kpis"] = [
        {
            "label": "Active Job Postings",
            "value": str(active_jobs),
            "trend": f"{len(jobs)} total job(s)",
            "icon": "bi-briefcase-fill",
            "tone": "gold",
            "hint": "Non-draft jobs created in your company workspace.",
        },
        {
            "label": "Applications Received",
            "value": str(total_apps),
            "trend": f"Avg CV score: {avg_score}%" if avg_score is not None else "Upload or sync CVs",
            "icon": "bi-people-fill",
            "tone": "green",
            "hint": "Total CVs evaluated against your job CV scoring metrics.",
        },
        {
            "label": "AI Shortlisted",
            "value": str(shortlisted_count),
            "trend": (
                f"{round((shortlisted_count / total_apps) * 100)}% pass rate"
                if total_apps
                else "No CVs scored yet"
            ),
            "icon": "bi-stars",
            "tone": "purple",
            "hint": "Candidates meeting the job's minimum passing CV score and shortlist cap.",
        },
        {
            "label": "Interviews Scheduled",
            "value": str(interview_count),
            "trend": "Interview module next" if interview_count == 0 else "Active candidates",
            "icon": "bi-camera-video-fill",
            "tone": "teal",
            "hint": "Candidates invited or scheduled for AI interviews.",
        },
    ]

    if total_apps > 0 or jobs:
        base = max(total_apps, 1)
        shell["funnel"] = [
            {
                "stage": "Applied",
                "count": total_apps,
                "pct": 100 if total_apps else 0,
                "css": "post",
            },
            {
                "stage": "Evaluated",
                "count": total_apps,
                "pct": 100 if total_apps else 0,
                "css": "screen",
            },
            {
                "stage": "Shortlisted",
                "count": shortlisted_count,
                "pct": round((shortlisted_count / base) * 100) if total_apps else 0,
                "css": "interview",
            },
            {
                "stage": "Interview",
                "count": interview_count,
                "pct": round((interview_count / base) * 100) if total_apps else 0,
                "css": "decide",
            },
        ]

    if total_apps > 0:
        shell["kanban"] = [
            {
                "title": "Evaluated (Screened)",
                "count": len(screened),
                "candidates": [{"name": c["name"], "role": c["role"], "score": c["score"]} for c in screened[:12]],
            },
            {
                "title": "Shortlisted",
                "count": shortlisted_count,
                "candidates": [
                    {"name": c["name"], "role": c["role"], "score": c["score"]} for c in shortlisted[:12]
                ],
            },
            {
                "title": "Interviewing",
                "count": interview_count,
                "candidates": [
                    {"name": c["name"], "role": c["role"], "score": c["score"]} for c in interviewing[:12]
                ],
            },
            {
                "title": "Not Progressing",
                "count": len(rejected),
                "candidates": [{"name": c["name"], "role": c["role"], "score": c["score"]} for c in rejected[:12]],
            },
        ]

    activity = []
    for c in candidates[:5]:
        badge = "Shortlisted" if c["status"] == "shortlisted" else ("Not progressing" if c["status"] == "rejected" else "Screened")
        activity.append(
            {
                "tone": "green" if c["status"] == "shortlisted" else "gold",
                "icon": "bi-file-earmark-check-fill",
                "text": (
                    f"<strong>{escape(c['name'])}</strong> scored <strong>{c['overall_score']}%</strong> "
                    f"for <strong>{escape(c['role'])}</strong>"
                ),
                "meta": f"{badge} · {c['applied']}",
            }
        )

    # Real scheduled interviews from DB
    interviews_qs = (
        InterviewSchedule.objects.filter(application__job_posting__company=company)
        .select_related("application__candidate", "application__job_posting")
        .order_by("-scheduled_start")[:25]
    )
    interview_rows = []
    for s in interviews_qs:
        candidate_name = s.application.candidate.full_name
        role = s.application.job_posting.title
        iv = s.interviews.first()
        status_label = "Scheduled"
        if iv:
            if iv.status == "completed":
                status_label = "Completed"
            elif iv.status == "in_progress":
                status_label = "In Progress"

        stage_name = "Stage 1: Screening"
        if iv:
            st = iv.stages.filter(status__in=["in_progress", "completed"]).order_by("-sequence_order").first()
            if st:
                stage_name = f"Stage {st.sequence_order}: {st.stage_type.title()}"

        interview_rows.append(
            {
                "candidate": candidate_name,
                "role": role,
                "stage": stage_name,
                "date": s.scheduled_start.strftime("%d %b %Y"),
                "time": s.scheduled_start.strftime("%I:%M %p"),
                "status": "completed" if status_label == "Completed" else "scheduled",
            }
        )
    shell["interviews"] = interview_rows

    shell["activity"] = activity
    shell["candidates"] = candidates
    return shell
