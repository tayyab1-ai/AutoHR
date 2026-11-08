import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .decorators import hr_login_required
from .form_catalog import catalog_for_api
from .form_config_services import (
    get_or_create_job_form_config,
    recruitment_google_connected,
    save_job_form_config,
)
from .google_forms_service import create_candidate_application_form
from .profile_services import ensure_profile_setup, is_profile_complete
from .models import JobPosting
from .services import get_job_for_company, inject_apply_link_into_job_description, save_finalized_job_description

_logger = logging.getLogger(__name__)


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _session_actor(request):
    return request.user.db_user.company, request.user.db_user


@hr_login_required
@require_GET
def job_form_config_api(request, job_id):
    company, user = _session_actor(request)
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    cfg = get_or_create_job_form_config(job)
    setup = ensure_profile_setup(user)
    step3 = (setup.step_data or {}).get("3") or {}
    return JsonResponse(
        {
            "ok": True,
            "catalog": catalog_for_api(),
            "config": {
                "application_form_title": cfg.application_form_title,
                "form_description": cfg.form_description,
                "selected_fields": cfg.selected_fields or [],
                "allow_multiple_responses": cfg.allow_multiple_responses,
                "google_form_id": cfg.google_form_id,
                "google_form_url": cfg.google_form_url,
                "resume_drive_folder_url": cfg.resume_drive_folder_url or "",
                "status": cfg.status,
            },
            "job": {
                "id": str(job.id),
                "title": job.title,
                "application_deadline": job.application_deadline.isoformat() if job.application_deadline else "",
            },
            "google_connected": recruitment_google_connected(user.id),
            "profile_defaults": step3,
        }
    )


@hr_login_required
@require_POST
def job_form_config_save(request, job_id):
    company, user = _session_actor(request)
    if not is_profile_complete(user):
        return JsonResponse(
            {"ok": False, "profile_required": True, "errors": {"profile": ["Complete profile setup first."]}},
            status=403,
        )
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    errors = save_job_form_config(job, _json_body(request))
    if errors:
        return JsonResponse({"ok": False, "errors": {"__all__": errors}}, status=400)
    cfg = get_or_create_job_form_config(job)
    return JsonResponse({"ok": True, "message": "Form configuration saved.", "config_id": str(cfg.id)})


@hr_login_required
@require_POST
def job_create_google_form(request, job_id):
    """Create form in Google; HR must confirm before we attach the link to the job description."""
    company, user = _session_actor(request)
    if not is_profile_complete(user):
        return JsonResponse(
            {"ok": False, "profile_required": True, "errors": {"profile": ["Complete profile setup first."]}},
            status=403,
        )
    if not recruitment_google_connected(user.id):
        return JsonResponse(
            {"ok": False, "errors": {"google": ["Connect Google in profile step 3 before creating forms."]}},
            status=400,
        )
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    data = _json_body(request)
    finalized = (data.get("finalized_jd") or "").strip()
    if finalized:
        save_finalized_job_description(job, finalized)

    cfg = get_or_create_job_form_config(job)
    if data.get("selected_fields"):
        cfg_errors = save_job_form_config(job, data)
        if cfg_errors:
            return JsonResponse({"ok": False, "errors": {"__all__": cfg_errors}}, status=400)

    cfg.refresh_from_db()
    if not cfg.selected_fields:
        return JsonResponse({"ok": False, "errors": {"fields": ["Select at least one question."]}}, status=400)

    title = cfg.application_form_title or f"{job.title} - Candidate Application"
    description = cfg.form_description or ""

    try:
        form_id, form_url, editor_url = create_candidate_application_form(
            user.id,
            title=title,
            description=description,
            selected_field_keys=list(cfg.selected_fields),
        )
    except RuntimeError as exc:
        return JsonResponse(
            {
                "ok": False,
                "errors": {"google": [str(exc)]},
                "integrations_settings": True,
            },
            status=502,
        )
    except Exception as exc:
        _logger.exception("Google Form creation failed for job %s", job_id)
        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "google": [
                        "Google Form creation failed. Open Account → Integrations, reconnect Google Workspace, "
                        "and ensure Google Forms API is enabled in Cloud Console."
                    ]
                },
                "integrations_settings": True,
            },
            status=502,
        )

    cfg.google_form_id = form_id
    cfg.google_form_url = form_url
    cfg.status = "pending_review"
    cfg.save(update_fields=["google_form_id", "google_form_url", "status", "updated_at"])

    return JsonResponse(
        {
            "ok": True,
            "message": "Google Form created. Review the link, add a resume question manually if needed, then continue.",
            "form_id": form_id,
            "form_url": form_url,
            "form_edit_url": editor_url,
            "resume_upload_note": (
                "Resume upload is not added automatically. In Google Forms, add a File upload question manually, then continue."
            ),
        }
    )


@hr_login_required
@require_POST
def job_confirm_google_form(request, job_id):
    """After HR reviews the form, save link to DB and inject into job description."""
    company, user = _session_actor(request)
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "errors": {"job": ["Job not found."]}}, status=404)

    cfg = get_or_create_job_form_config(job)
    data = _json_body(request)
    form_url = (data.get("form_url") or cfg.google_form_url or "").strip()
    if not form_url:
        return JsonResponse(
            {"ok": False, "errors": {"form_url": ["Generate a Google Form first or paste the form link."]}},
            status=400,
        )

    folder_url = (data.get("resume_drive_folder_url") or "").strip()[:500]
    cfg.google_form_url = form_url
    cfg.resume_drive_folder_url = folder_url or None
    cfg.status = "active"
    cfg.save(update_fields=["google_form_url", "resume_drive_folder_url", "status", "updated_at"])

    try:
        job = inject_apply_link_into_job_description(job, form_url)
    except ValueError as exc:
        return JsonResponse({"ok": False, "errors": {"form_url": [str(exc)]}}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "message": "Application link added to your job description and saved.",
            "form_url": form_url,
            "finalized_jd": job.approved_jd_content,
        }
    )
