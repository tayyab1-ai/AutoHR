from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from . import data
from .dev_actor import ensure_demo_hr
from .forms import JobIntakeForm
from .services import create_job_posting, jobs_for_dashboard


def landing(request):
    return render(request, "landing.html")


def auth_page(request, mode="signup"):
    context = {
        "mode": mode,
        "is_signup": mode == "signup",
    }
    return render(request, "auth.html", context)


def dashboard(request):
    company, user = ensure_demo_hr()
    db_jobs = jobs_for_dashboard(company)
    jobs = db_jobs if db_jobs else data.JOBS

    hr = {
        **data.HR_ACCOUNT,
        "full_name": user.full_name,
        "email": user.email,
        "job_title": user.job_title or data.HR_ACCOUNT["job_title"],
        "company_name": company.name,
    }

    context = {
        "hr": hr,
        "company_name": company.name,
        "job_form": JobIntakeForm(company_name=company.name),
        "kpis": data.KPI_CARDS,
        "funnel": data.PIPELINE_FUNNEL,
        "activity": data.RECENT_ACTIVITY,
        "jobs": jobs,
        "candidates": data.CANDIDATES,
        "interviews": data.INTERVIEWS,
        "kanban": data.KANBAN_COLUMNS,
        "reports": data.REPORTS_SUMMARY,
        "chart_months": data.CHART_MONTHS,
        "chart_values": data.CHART_APPLICATIONS,
        "chart_max": max(data.CHART_APPLICATIONS),
    }
    return render(request, "dashboard.html", context)


@require_POST
def create_job_post(request):
    company, user = ensure_demo_hr()
    form = JobIntakeForm(request.POST, company_name=company.name)
    form.expected_company_name = company.name

    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    job = create_job_posting(company, user, form.cleaned_data)
    return JsonResponse(
        {
            "ok": True,
            "job_id": str(job.id),
            "title": job.title,
            "message": "Job saved as draft. AI job description generation will be added in the next step.",
        }
    )
