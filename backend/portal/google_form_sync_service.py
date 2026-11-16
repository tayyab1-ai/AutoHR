"""Automated and periodic sync worker for Google Form candidate responses.

Pulls responses from Google Forms API v1, downloads attached CV files via Google Drive
API v3 (if present), falls back to structured resume synthesis from form fields,
and scores candidates through the existing cv_scoring_service pipeline.
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .cv_scoring_service import score_candidate_cv_for_job
from .form_catalog import FORM_SECTIONS
from .google_oauth import get_credentials
from .models import Application, JobPosting, User
from .profile_models import JobApplicationFormConfig

_logger = logging.getLogger(__name__)


def resolve_google_workspace_credentials(job: JobPosting, user_id=None):
    """Resolve active Google Workspace credentials for the job or user."""
    # 1. Direct user_id if passed
    if user_id:
        creds = get_credentials(user_id, "google_workspace")
        if creds and creds.token:
            return creds

    # 2. Job creator
    if job.created_by_id:
        creds = get_credentials(job.created_by_id, "google_workspace")
        if creds and creds.token:
            return creds

    # 3. Any HR user in the same company
    company_users = User.objects.filter(company=job.company).values_list("id", flat=True)
    for uid in company_users:
        creds = get_credentials(uid, "google_workspace")
        if creds and creds.token:
            return creds

    # Never fall back to another company's Google account.
    return None


def _normalize_title(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", (text or "").lower())
    return " ".join(cleaned.split())


# Catalog field alias dictionary
_FIELD_ALIASES: dict[str, list[str]] = {
    "full_name": ["full name", "name", "candidate name", "your name"],
    "email": ["email", "email address", "candidate email", "work email", "contact email"],
    "phone": ["phone", "phone number", "mobile", "contact number", "whatsapp"],
    "current_city": ["current city", "city", "location", "residence"],
    "country": ["country"],
    "linkedin": ["linkedin", "linkedin profile", "linkedin url"],
    "github": ["github", "github profile", "github url"],
    "portfolio": ["portfolio", "website", "personal website", "portfolio website"],
    "education_level": ["highest education level", "education level", "qualification level"],
    "degree": ["degree", "degree qualification", "qualification"],
    "field_of_study": ["field of study", "major", "specialization"],
    "university": ["university", "institute", "college", "institution"],
    "graduation_year": ["graduation year", "year of graduation"],
    "currently_studying": ["currently studying", "are you studying"],
    "total_experience_years": ["total professional experience", "total experience", "years of experience"],
    "relevant_experience_years": ["relevant experience", "years of relevant experience"],
    "employment_status": ["current employment status", "employment status"],
    "current_company": ["current company", "organization", "current employer"],
    "current_job_title": ["current job title", "job title", "designation", "role"],
    "previous_company": ["previous company", "past employer"],
    "previous_job_title": ["previous job title", "previous designation"],
    "notice_period": ["notice period", "availability"],
    "expected_salary": ["expected salary", "expected remuneration", "salary expectation"],
    "available_to_join": ["available to join", "joining date", "earliest start date"],
    "primary_skills": ["primary technical skills", "primary skills", "core skills", "skills"],
    "programming_languages": ["programming languages", "languages"],
    "frameworks": ["frameworks and libraries", "frameworks", "libraries"],
    "tools": ["tools and technologies", "tools"],
    "certifications": ["relevant certifications", "certifications"],
    "job_technologies": ["experience with required job technologies", "required technologies"],
    "has_projects": ["have you worked on professional or personal projects"],
    "recent_project_name": ["most recent relevant project name", "project name", "recent project"],
    "project_description": ["explain the most relevant project", "project description", "project details"],
    "project_role": ["what was your role in this project", "project role"],
    "project_technologies": ["which technologies and tools did you use", "project technologies"],
    "project_problem": ["what problem did the project solve", "problem solved"],
    "project_challenges": ["what challenges did you face", "project challenges"],
    "project_outcome": ["what was the outcome or impact", "project outcome", "project impact"],
    "project_link": ["project github live demo link", "project link", "demo link"],
    "why_interested": ["why are you interested in this position", "why interested"],
    "why_suitable": ["why do you think you are a suitable candidate", "why suitable"],
    "what_different": ["what makes you different from other applicants", "what makes you unique"],
    "comfortable_requirements": ["are you comfortable with the job requirements"],
    "when_can_join": ["when can you join"],
    "anything_else": ["anything else you want us to know", "additional information", "comments"],
    "resume_file": ["upload resume", "upload cv", "resume", "cv", "attach resume", "curriculum vitae"],
}


def _match_question_key(title: str) -> str:
    norm = _normalize_title(title)
    for key, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if alias in norm or norm in alias:
                return key
    return norm.replace(" ", "_")[:64]


def _extract_drive_file_id(value: str) -> str | None:
    if not value or not isinstance(value, str):
        return None
    # Check for direct ID or standard Drive patterns
    patterns = [
        r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"docs\.google\.com/file/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, value)
        if m:
            return m.group(1)
    return None


def _download_drive_file(creds, file_id: str) -> SimpleUploadedFile | None:
    """Download file bytes via Google Drive API v3."""
    try:
        drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        meta = drive_service.files().get(fileId=file_id, fields="id, name, mimeType, size").execute()
        filename = meta.get("name", "resume.pdf")
        mime = meta.get("mimeType", "application/pdf")

        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        content = fh.getvalue()
        if content:
            return SimpleUploadedFile(name=filename, content=content, content_type=mime)
    except Exception as exc:
        _logger.warning("Could not download file %s from Drive: %s", file_id, exc)
    return None


def _build_cv_text_from_answers(answers: dict[str, Any]) -> str:
    """Synthesize full candidate resume text from structured application answers."""
    full_name = answers.get("full_name") or "Candidate"
    email = answers.get("email") or ""
    phone = answers.get("phone") or ""
    city = answers.get("current_city") or ""
    country = answers.get("country") or ""
    location = f"{city}, {country}".strip(", ")
    linkedin = answers.get("linkedin") or ""
    github = answers.get("github") or ""
    portfolio = answers.get("portfolio") or ""

    degree = answers.get("degree") or answers.get("education_level") or "Bachelor's"
    field_of_study = answers.get("field_of_study") or ""
    university = answers.get("university") or ""
    grad_year = answers.get("graduation_year") or ""

    total_exp = answers.get("total_experience_years") or "0"
    relevant_exp = answers.get("relevant_experience_years") or total_exp
    curr_company = answers.get("current_company") or ""
    curr_title = answers.get("current_job_title") or ""
    emp_status = answers.get("employment_status") or ""

    skills = answers.get("primary_skills") or ""
    languages = answers.get("programming_languages") or ""
    frameworks = answers.get("frameworks") or ""
    tools = answers.get("tools") or ""
    job_tech = answers.get("job_technologies") or ""
    certifications = answers.get("certifications") or ""

    project_name = answers.get("recent_project_name") or ""
    project_role = answers.get("project_role") or ""
    project_tech = answers.get("project_technologies") or ""
    project_desc = answers.get("project_description") or ""
    project_problem = answers.get("project_problem") or ""
    project_challenges = answers.get("project_challenges") or ""
    project_outcome = answers.get("project_outcome") or ""

    why_suitable = answers.get("why_suitable") or ""
    why_interested = answers.get("why_interested") or ""
    what_different = answers.get("what_different") or ""

    lines = [
        f"FULL NAME: {full_name}",
        f"EMAIL: {email}",
        f"PHONE: {phone}",
        f"LOCATION: {location}",
        f"LINKEDIN: {linkedin}",
        f"GITHUB: {github}",
        f"PORTFOLIO: {portfolio}",
        "",
        "PROFESSIONAL SUMMARY & FIT:",
        f"Suitability: {why_suitable}",
        f"Interest: {why_interested}",
        f"Key Differentiator: {what_different}",
        "",
        "EDUCATION:",
        f"Degree: {degree} in {field_of_study}".strip(),
        f"Institution: {university} ({grad_year})".strip(),
        f"Education Level: {answers.get('education_level', '')}",
        "",
        "PROFESSIONAL EXPERIENCE:",
        f"Total Experience: {total_exp} years (Relevant: {relevant_exp} years)",
        f"Current Position: {curr_title} at {curr_company} ({emp_status})".strip(),
        f"Notice Period: {answers.get('notice_period', 'Immediate')}",
        "",
        "TECHNICAL SKILLS & EXPERTISE:",
        f"Primary Skills: {skills}",
        f"Programming Languages: {languages}",
        f"Frameworks & Libraries: {frameworks}",
        f"Tools & Platforms: {tools}",
        f"Required Job Technologies: {job_tech}",
        f"Certifications: {certifications}",
        "",
        "REPRESENTATIVE PROJECT:",
        f"Project Name: {project_name}",
        f"Role: {project_role}",
        f"Technologies: {project_tech}",
        f"Description: {project_desc}",
        f"Problem Solved: {project_problem}",
        f"Challenges Overcome: {project_challenges}",
        f"Impact / Outcome: {project_outcome}",
        f"Project URL: {answers.get('project_link', '')}",
    ]
    return "\n".join([line for line in lines if line is not None])


def sync_job_form_responses(
    job: JobPosting,
    *,
    user_id=None,
    force_rescore: bool = False,
) -> dict[str, Any]:
    """Sync candidate submissions from Google Forms for a given job.

    Idempotent: skips responses whose `responseId` has already been recorded in
    `Application.source_message_id`, unless `force_rescore=True`.
    """
    cfg = JobApplicationFormConfig.objects.filter(job_id=job.id).first()
    if not cfg or not cfg.google_form_id:
        return {
            "ok": False,
            "job_id": str(job.id),
            "job_title": job.title,
            "synced_count": 0,
            "message": "No Google Form is configured for this job.",
        }

    form_id = cfg.google_form_id.strip()
    creds = resolve_google_workspace_credentials(job, user_id=user_id)
    if not creds:
        return {
            "ok": False,
            "job_id": str(job.id),
            "job_title": job.title,
            "synced_count": 0,
            "message": "Google Workspace is not connected. Reconnect Google in Profile -> Integrations.",
        }

    try:
        forms_service = build("forms", "v1", credentials=creds, cache_discovery=False)
        form_meta = forms_service.forms().get(formId=form_id).execute()
    except Exception as exc:  # HttpError, network or token-refresh failures
        _logger.warning("Forms API get failed for form %s: %s", form_id, exc)
        return {
            "ok": False,
            "job_id": str(job.id),
            "job_title": job.title,
            "synced_count": 0,
            "message": f"Google Forms API error: {exc}",
        }

    # Build questionId -> metadata map
    question_map: dict[str, dict] = {}
    for item in form_meta.get("items", []):
        q_item = item.get("questionItem")
        if not q_item:
            continue
        q = q_item.get("question") or {}
        qid = q.get("questionId")
        if qid:
            title = item.get("title", "")
            catalog_key = _match_question_key(title)
            question_map[qid] = {
                "title": title,
                "key": catalog_key,
                "question": q,
            }

    try:
        responses_data = forms_service.forms().responses().list(formId=form_id).execute()
    except Exception as exc:  # HttpError, network or token-refresh failures
        _logger.warning("Forms API responses.list failed for form %s: %s", form_id, exc)
        return {
            "ok": False,
            "job_id": str(job.id),
            "job_title": job.title,
            "synced_count": 0,
            "message": f"Could not list Google Form responses: {exc}",
        }

    items = responses_data.get("responses", [])
    if not items:
        return {
            "ok": True,
            "job_id": str(job.id),
            "job_title": job.title,
            "total_responses": 0,
            "synced_count": 0,
            "message": "No responses submitted yet.",
        }

    existing_message_ids = set(
        Application.objects.filter(job_posting=job)
        .exclude(source_message_id__isnull=True)
        .exclude(source_message_id="")
        .values_list("source_message_id", flat=True)
    )

    synced_apps = []
    skipped_count = 0
    errors: list[str] = []

    for resp in items:
        response_id = resp.get("responseId") or ""
        if not response_id:
            continue
        if not force_rescore and response_id in existing_message_ids:
            skipped_count += 1
            continue

        raw_answers = resp.get("answers", {})
        extracted_answers: dict[str, Any] = {}
        uploaded_file: SimpleUploadedFile | None = None
        candidate_drive_file_id: str | None = None

        for qid, ans_block in raw_answers.items():
            meta = question_map.get(qid)
            key = meta["key"] if meta else f"q_{qid}"

            # Text answers
            text_answers = ans_block.get("textAnswers", {}).get("answers", [])
            val = ", ".join([a.get("value", "") for a in text_answers if a.get("value")])
            extracted_answers[key] = val

            # Check for drive link in text answer
            if not candidate_drive_file_id:
                candidate_drive_file_id = _extract_drive_file_id(val)

            # File upload answers (Google Forms file upload question)
            file_answers = ans_block.get("fileUploadAnswers", {}).get("answers", [])
            if file_answers and not candidate_drive_file_id:
                candidate_drive_file_id = file_answers[0].get("fileId")

        # If we have a Drive file ID, attempt downloading
        if candidate_drive_file_id:
            uploaded_file = _download_drive_file(creds, candidate_drive_file_id)

        # Build fallback / synthetic CV text
        cv_text = _build_cv_text_from_answers(extracted_answers)

        email = (extracted_answers.get("email") or resp.get("respondentEmail") or "").strip().lower()
        full_name = (extracted_answers.get("full_name") or "").strip()
        phone = (extracted_answers.get("phone") or "").strip()
        city = (extracted_answers.get("current_city") or "").strip()
        country = (extracted_answers.get("country") or "").strip()
        location = f"{city}, {country}".strip(", ")

        if not email:
            # Look for email regex in all values
            m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", json.dumps(extracted_answers))
            if m:
                email = m.group(0).lower()

        if not email:
            errors.append(f"Response {response_id} skipped: Candidate email missing.")
            continue

        try:
            app = score_candidate_cv_for_job(
                job,
                uploaded_file=uploaded_file,
                resume_text=cv_text,
                full_name=full_name,
                email=email,
                phone=phone,
                location=location,
                source="web_form",
                source_message_id=response_id,
            )
            synced_apps.append(
                {
                    "application_id": str(app.id),
                    "candidate_name": app.candidate.full_name,
                    "candidate_email": app.candidate.email,
                    "score": float(app.cv_evaluation.overall_score) if hasattr(app, "cv_evaluation") else None,
                    "status": app.status,
                }
            )
        except Exception as exc:
            _logger.exception("Failed scoring form response %s for job %s: %s", response_id, job.id, exc)
            errors.append(f"Response {response_id} failed: {exc}")

    return {
        "ok": True,
        "job_id": str(job.id),
        "job_title": job.title,
        "total_responses": len(items),
        "synced_count": len(synced_apps),
        "skipped_count": skipped_count,
        "applications": synced_apps,
        "errors": errors,
        "message": f"Successfully synced {len(synced_apps)} new response(s).",
    }


def sync_all_active_forms(*, company=None, user_id=None) -> dict[str, Any]:
    """Sync candidate responses for all active jobs with configured Google Forms."""
    configs_qs = JobApplicationFormConfig.objects.exclude(google_form_id__isnull=True).exclude(
        google_form_id=""
    )
    if company:
        configs_qs = configs_qs.filter(company_id=company.id)

    total_synced = 0
    job_results = []
    job_ids = list(configs_qs.values_list("job_id", flat=True))

    jobs = JobPosting.objects.filter(id__in=job_ids)
    for job in jobs:
        try:
            res = sync_job_form_responses(job, user_id=user_id)
        except Exception as exc:  # one bad job must not stop the others
            _logger.exception("Form sync failed for job %s", job.id)
            res = {
                "ok": False,
                "job_id": str(job.id),
                "job_title": job.title,
                "synced_count": 0,
                "message": f"Sync failed: {exc}",
                "errors": [str(exc)],
            }
        job_results.append(res)
        total_synced += res.get("synced_count", 0)

    return {
        "ok": True,
        "jobs_checked": len(jobs),
        "total_synced": total_synced,
        "results": job_results,
    }

