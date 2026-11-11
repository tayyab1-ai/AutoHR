"""Views for per-job CV scoring metrics configuration, CV evaluation, and manual shortlist overrides."""

import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .cv_scoring_service import (
    apply_manual_decision,
    score_candidate_cv_for_job,
    serialize_application,
)
from .decorators import hr_login_required
from .models import Application, JobPosting
from .services import get_job_for_company, jobs_for_dashboard, update_job_cv_metrics
from .session_user import workspace_shell_for_company


def _parse_int(value, label: str) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number.")


def _company_snapshot(company) -> dict:
    jobs = jobs_for_dashboard(company)
    shell = workspace_shell_for_company(company, jobs=jobs)
    return {
        "candidates": shell["candidates"],
        "kpis": shell["kpis"],
        "jobs": jobs,
    }


@hr_login_required
@require_POST
def update_job_cv_metrics_api(request, job_id):
    company = request.user.db_user.company
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)
    else:
        payload = request.POST

    try:
        skill_w = _parse_int(payload.get("cv_skill_weight"), "Skills weight")
        exp_w = _parse_int(payload.get("cv_experience_weight"), "Experience weight")
        edu_w = _parse_int(payload.get("cv_education_weight"), "Education weight")
        min_pass = _parse_int(payload.get("cv_min_passing_score"), "Minimum passing score")
        raw_cap = payload.get("shortlist_after_cv_count")
        cap = _parse_int(raw_cap, "Shortlist count") if str(raw_cap or "").strip() else None

        job, updated_count = update_job_cv_metrics(
            job,
            skill_weight=skill_w,
            experience_weight=exp_w,
            education_weight=edu_w,
            min_passing_score=min_pass,
            shortlist_after_cv_count=cap,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    snapshot = _company_snapshot(company)
    return JsonResponse(
        {
            "ok": True,
            "message": (
                f"CV scoring metrics saved ({job.cv_skill_weight}/{job.cv_experience_weight}/{job.cv_education_weight}, "
                f"pass >= {job.cv_min_passing_score}%). Recalculated {updated_count} application(s)."
            ),
            "job_metrics": {
                "id": str(job.id),
                "cv_skill_weight": job.cv_skill_weight,
                "cv_experience_weight": job.cv_experience_weight,
                "cv_education_weight": job.cv_education_weight,
                "cv_min_passing_score": job.cv_min_passing_score,
                "shortlist_after_cv_count": job.shortlist_after_cv_count,
            },
            **snapshot,
        }
    )


@hr_login_required
@require_POST
def score_cv_api(request):
    company = request.user.db_user.company
    job_id = (request.POST.get("job_id") or "").strip()
    if not job_id:
        return JsonResponse({"ok": False, "error": "Select a job posting first."}, status=400)
    try:
        job = get_job_for_company(job_id, company)
    except (JobPosting.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    uploaded_file = request.FILES.get("resume_file")
    pasted_text = request.POST.get("resume_text") or ""
    full_name = request.POST.get("full_name") or ""
    email = request.POST.get("email") or ""
    phone = request.POST.get("phone") or ""
    location = request.POST.get("location") or ""

    try:
        app = score_candidate_cv_for_job(
            job,
            uploaded_file=uploaded_file,
            resume_text=pasted_text,
            full_name=full_name,
            email=email,
            phone=phone,
            location=location,
            source="manual_upload",
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    snapshot = _company_snapshot(company)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Scored CV for {app.candidate.full_name}.",
            "application": serialize_application(app),
            **snapshot,
        }
    )


@hr_login_required
@require_POST
def application_decision_api(request, application_id):
    company = request.user.db_user.company
    try:
        app = Application.objects.select_related("job_posting", "candidate").get(
            id=application_id,
            job_posting__company=company,
        )
    except (Application.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "Application not found."}, status=404)

    if request.content_type and "application/json" in request.content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)
    else:
        payload = request.POST

    decision = (payload.get("decision") or "").strip().lower()
    try:
        updated = apply_manual_decision(app, decision)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    snapshot = _company_snapshot(company)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Updated {updated.candidate.full_name} to {updated.status}.",
            "application": serialize_application(updated),
            **snapshot,
        }
    )

