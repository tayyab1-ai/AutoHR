from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .decorators import hr_login_required
from .forms import JobIntakeForm
from .models import JobPosting
from .profile_services import ensure_profile_setup, is_profile_complete
from .services import (
    create_job_posting,
    draft_jobs_for_user,
    generate_ai_job_description,
    get_job_for_company,
    jobs_for_dashboard,
    save_finalized_job_description,
)
from .session_user import build_hr_profile, workspace_shell


def _session_actor(request):
    return request.user.db_user.company, request.user.db_user


def landing(request):
    if getattr(request.user, "is_authenticated", False) and hasattr(request.user, "db_user"):
        return redirect("dashboard")
    return render(request, "landing.html")


def auth_page(request, mode="signup"):
    if getattr(request.user, "is_authenticated", False) and hasattr(request.user, "db_user"):
        return redirect("dashboard")
    context = {
        "mode": mode,
        "is_signup": mode == "signup",
        "registered": request.GET.get("registered") == "1",
        "password_reset": request.GET.get("reset") == "1",
    }
    return render(request, "auth.html", context)


@ensure_csrf_cookie
@hr_login_required
def dashboard(request):
    company, user = _session_actor(request)
    ensure_profile_setup(user)
    jobs = jobs_for_dashboard(company)
    drafts = draft_jobs_for_user(company, user)
    draft_rows = [
        {
            "id": str(j.id),
            "title": j.title,
            "updated": j.updated_at.strftime("%d %b %Y %H:%M") if j.updated_at else "",
            "has_jd": bool((j.ai_generated_jd_draft or "").strip()),
        }
        for j in drafts
    ]
    shell = workspace_shell(active_jobs=len([j for j in jobs if j.get("status") != "draft"]))
    hr = build_hr_profile(user, company)
    pcomplete = is_profile_complete(user)

    context = {
        "hr": hr,
        "company_name": company.name,
        "job_form": JobIntakeForm(company_name=company.name),
        "jobs": jobs,
        "draft_jobs": draft_rows,
        "profile_complete": pcomplete,
        **shell,
    }
    return render(request, "dashboard.html", context)


@hr_login_required
@require_POST
def create_job_post(request):
    company, user = _session_actor(request)
    form = JobIntakeForm(request.POST, company_name=company.name)
    form.expected_company_name = company.name

    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    job = create_job_posting(company, user, form.cleaned_data)

    ai_error = None
    try:
        job = generate_ai_job_description(job)
    except RuntimeError as exc:
        ai_error = str(exc)

    payload = {
        "ok": True,
        "job_id": str(job.id),
        "title": job.title,
        "ai_ok": ai_error is None,
        "ai_generated_jd": job.ai_generated_jd_draft if ai_error is None else None,
        "message": "Job details saved.",
    }
    if ai_error:
        payload["errors"] = {"ai": [ai_error]}
        payload["message"] = (
            "Job details saved as draft, but AI could not generate a description yet. "
            "Fix the issue below and use Retry."
        )
    else:
        payload["message"] = "Job description generated. Review the draft below."

    return JsonResponse(payload)


@hr_login_required
@require_POST
def generate_job_jd(request, job_id):
    company, _user = _session_actor(request)
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    try:
        job = generate_ai_job_description(job)
    except RuntimeError as exc:
        return JsonResponse(
            {"ok": False, "errors": {"ai": [str(exc)]}},
            status=502,
        )

    return JsonResponse(
        {
            "ok": True,
            "job_id": str(job.id),
            "title": job.title,
            "ai_generated_jd": job.ai_generated_jd_draft,
        }
    )


@hr_login_required
@require_POST
def prepare_google_form(request, job_id):
    company, user = _session_actor(request)
    if not is_profile_complete(user):
        return JsonResponse(
            {
                "ok": False,
                "profile_required": True,
                "errors": {
                    "profile": [
                        "Complete your HR profile setup before continuing past the job description step."
                    ]
                },
            },
            status=403,
        )
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    finalized = (request.POST.get("finalized_jd") or "").strip()
    if not finalized:
        finalized = (job.ai_generated_jd_draft or "").strip()
    if not finalized:
        return JsonResponse(
            {
                "ok": False,
                "errors": {"finalized_jd": ["Add or generate a job description before continuing."]},
            },
            status=400,
        )

    save_finalized_job_description(job, finalized)
    return JsonResponse(
        {
            "ok": True,
            "job_id": str(job.id),
            "finalized_jd": job.approved_jd_content,
            "message": "Final job description saved. Google Form creation will be added in the next step.",
        }
    )


@hr_login_required
@require_POST
def delete_job_draft(request, job_id):
    company, user = _session_actor(request)
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)
    if job.created_by_id != user.id or job.status != "draft":
        return JsonResponse({"ok": False, "errors": {"job": ["Only your draft jobs can be deleted."]}}, status=403)
    job.delete()
    return JsonResponse({"ok": True, "message": "Draft deleted."})


@hr_login_required
@require_GET
def get_job_draft(request, job_id):
    company, user = _session_actor(request)
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)
    if job.created_by_id != user.id:
        return JsonResponse({"ok": False, "errors": {"job": ["Not allowed."]}}, status=403)
    return JsonResponse(
        {
            "ok": True,
            "job_id": str(job.id),
            "title": job.title,
            "status": job.status,
            "ai_generated_jd": job.ai_generated_jd_draft or "",
            "has_jd": bool((job.ai_generated_jd_draft or "").strip()),
        }
    )
