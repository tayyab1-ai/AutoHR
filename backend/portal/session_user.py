"""Helpers for the signed-in HR user and company."""


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
