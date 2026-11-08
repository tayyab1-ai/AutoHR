from django.utils import timezone

from .form_catalog import catalog_for_api, default_selected_field_keys
from .models import JobPosting
from .profile_models import IntegrationConnection, JobApplicationFormConfig


def get_or_create_job_form_config(job: JobPosting) -> JobApplicationFormConfig:
    cfg, created = JobApplicationFormConfig.objects.get_or_create(
        job_id=job.id,
        defaults={
            "company_id": job.company_id,
            "selected_fields": default_selected_field_keys(),
            "application_form_title": f"{job.title} - Candidate Application",
            "form_description": (
                f"Apply for {job.title} at {job.company.name}. "
                "Please complete all required fields accurately."
            ),
        },
    )
    if not created and not cfg.selected_fields:
        cfg.selected_fields = default_selected_field_keys()
        cfg.save(update_fields=["selected_fields", "updated_at"])
    return cfg


def save_job_form_config(job: JobPosting, data: dict) -> list[str]:
    errors = []
    selected = data.get("selected_fields")
    if not isinstance(selected, list) or not selected:
        errors.append("Select at least one form question.")
        return errors

    title = (data.get("application_form_title") or "").strip() or f"{job.title} - Candidate Application"
    desc = (data.get("form_description") or "").strip()
    if not desc:
        errors.append("Form description is required.")
        return errors

    cfg = get_or_create_job_form_config(job)
    cfg.application_form_title = title[:300]
    cfg.form_description = desc
    cfg.selected_fields = selected
    cfg.allow_multiple_responses = bool(data.get("allow_multiple_responses"))
    cfg.updated_at = timezone.now()
    cfg.save()
    return []


def recruitment_google_connected(user_id) -> bool:
    row = IntegrationConnection.objects.filter(user_id=user_id, provider="google_workspace").first()
    return bool(row and row.status == "connected")


def google_form_edit_url(cfg: JobApplicationFormConfig) -> str:
    if cfg and cfg.google_form_id:
        return f"https://docs.google.com/forms/d/{cfg.google_form_id}/edit"
    return ""


def job_draft_wizard_state(job: JobPosting) -> dict:
    """Where the create-job wizard should resume for a saved draft."""
    cfg = JobApplicationFormConfig.objects.filter(job_id=job.id).first()
    has_ai_jd = bool((job.ai_generated_jd_draft or "").strip())
    approved = bool((job.approved_jd_content or "").strip())
    form_url = (cfg.google_form_url or "").strip() if cfg else ""
    form_edit_url = google_form_edit_url(cfg) if cfg else ""

    if cfg and cfg.status == "active" and form_url:
        resume_step, resume_substep = 4, "complete"
    elif cfg and cfg.status == "pending_review" and form_url:
        resume_step, resume_substep = 3, "form_review"
    elif approved:
        resume_step, resume_substep = 3, "form_builder"
    elif has_ai_jd:
        resume_step, resume_substep = 2, "jd_editor"
    else:
        resume_step, resume_substep = 2, "jd_generate"

    jd_text = (job.approved_jd_content or job.ai_generated_jd_draft or "").strip()
    return {
        "resume_step": resume_step,
        "resume_substep": resume_substep,
        "ai_generated_jd": job.ai_generated_jd_draft or "",
        "approved_jd": job.approved_jd_content or "",
        "has_jd": has_ai_jd,
        "jd_text": jd_text,
        "form_url": form_url,
        "form_edit_url": form_edit_url,
        "resume_drive_folder_url": (cfg.resume_drive_folder_url or "").strip() if cfg else "",
        "form_config_status": (cfg.status if cfg else "draft") or "draft",
    }
