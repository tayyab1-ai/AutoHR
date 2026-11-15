"""CV parsing, Groq AI rubric scoring, weighted evaluation, and shortlisting."""

from __future__ import annotations

import io
import json
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from docx import Document
from pypdf import PdfReader

from .groq_jd import call_groq_chat, groq_model_name
from .models import Application, Candidate, CvEvaluation, JobPosting, ParsedCv

MAX_RESUME_BYTES = 10 * 1024 * 1024
PRE_INTERVIEW_STATUSES = {"applied", "parsing_cv", "screened", "shortlisted"}
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _quantize_2(value: float | Decimal | int | str) -> Decimal:
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        dec = Decimal("0")
    clamped = max(Decimal("0"), min(Decimal("100"), dec))
    return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_exp_years(value) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if dec < 0:
        return Decimal("0.0")
    return min(Decimal("60.0"), dec).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _clean_string_list(items, *, limit: int = 30, item_max: int = 180) -> list[str]:
    if not isinstance(items, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        val = str(raw or "").strip()
        if not val:
            continue
        val = val[:item_max]
        key = val.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(val)
        if len(out) >= limit:
            break
    return out


def _extract_pdf_text(raw_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw_bytes))
    chunks = []
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if text:
            chunks.append(text)
    return "\n\n".join(chunks).strip()


def _extract_docx_text(raw_bytes: bytes) -> str:
    doc = Document(io.BytesIO(raw_bytes))
    parts: list[str] = []
    for para in doc.paragraphs:
        txt = (para.text or "").strip()
        if txt:
            parts.append(txt)
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text and cell.text.strip()]
            if row_cells:
                parts.append(" | ".join(row_cells))
    return "\n".join(parts).strip()


def _decode_plain_text(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore").strip()


def extract_resume_content(*, uploaded_file=None, pasted_text: str = "") -> tuple[str, bytes, str, str]:
    """Extract CV text from an uploaded PDF/DOCX/TXT file or pasted text."""
    if uploaded_file is not None:
        raw_bytes = uploaded_file.read()
        if not raw_bytes:
            raise ValueError("Uploaded file is empty.")
        if len(raw_bytes) > MAX_RESUME_BYTES:
            raise ValueError("CV file is too large (maximum 10 MB).")

        filename = (uploaded_file.name or "resume.txt").strip()
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError("Unsupported CV format. Please upload a PDF, DOCX, or TXT file.")

        if ext == ".pdf":
            text = _extract_pdf_text(raw_bytes)
            mime = uploaded_file.content_type or "application/pdf"
        elif ext == ".docx":
            text = _extract_docx_text(raw_bytes)
            mime = (
                uploaded_file.content_type
                or "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            text = _decode_plain_text(raw_bytes)
            mime = uploaded_file.content_type or "text/plain"

        if len(re.sub(r"\s+", "", text)) < 30:
            raise ValueError(
                "Could not extract enough readable text from this file. "
                "If it is a scanned image PDF, paste the CV text instead."
            )
        return text, raw_bytes, filename[:255], mime[:100]

    cleaned = (pasted_text or "").strip()
    if len(re.sub(r"\s+", "", cleaned)) < 30:
        raise ValueError("Upload a CV file (PDF/DOCX/TXT) or paste at least a short resume text.")
    return cleaned, cleaned.encode("utf-8"), "pasted_cv.txt", "text/plain"


def _save_resume_blob(job_id: uuid.UUID, filename: str, raw_bytes: bytes) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or "resume.txt"
    rel_dir = Path("resumes") / str(job_id)
    target_dir = Path(settings.MEDIA_ROOT) / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:10]}_{safe_name}"
    (target_dir / stored_name).write_bytes(raw_bytes)
    media_prefix = "/" + settings.MEDIA_URL.strip("/")
    return f"{media_prefix}/resumes/{job_id}/{stored_name}"


def _parse_json_response(raw_output: str) -> dict:
    cleaned = (raw_output or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        parsed = json.loads(match.group(0))
        if isinstance(parsed, dict):
            return parsed
    raise RuntimeError("AI returned invalid JSON while scoring the CV.")


def _score_cv_with_groq(job: JobPosting, raw_text: str, hints: dict | None = None) -> dict:
    hints = hints or {}
    responsibilities = [
        r.body for r in job.responsibilities.filter(kind="key_responsibility").order_by("sort_order")
    ]
    exp_range = (
        f"{job.min_experience_years} to {job.max_experience_years} years"
        if job.max_experience_years is not None
        else f"{job.min_experience_years}+ years"
    )
    jd_excerpt = (job.approved_jd_content or job.ai_generated_jd_draft or job.job_description or "")[:3000]

    system = (
        "You are an objective, evidence-based technical recruiter and ATS evaluator. "
        "Parse the candidate CV text and evaluate fit strictly against the job requirements provided. "
        "Do NOT invent skills, companies, degrees, or years of experience that are not in the CV. "
        "Return valid JSON only with the exact schema requested. "
        "Score each of the three criteria independently from 0 to 100:\n"
        "- skill_match_score (0-100): Coverage and depth of required skills, programming languages, frameworks, tools, and cloud platforms.\n"
        "- experience_match_score (0-100): Alignment of total years and relevance of prior roles against required experience, responsibilities, and fresh-grad eligibility.\n"
        "- education_match_score (0-100): Alignment of highest degree and field of study against minimum education level."
    )

    schema_instructions = {
        "candidate": {
            "full_name": "string",
            "email": "string or empty",
            "phone": "string or empty",
            "location": "string or empty",
            "linkedin_url": "string or empty",
        },
        "parsed_cv": {
            "highest_degree": "string or empty",
            "experience_years": "number or null",
            "extracted_skills": ["string"],
            "experience_summary": "1-2 sentence factual summary",
            "education_summary": "1-2 sentence factual summary",
            "work_history": [{"title": "string", "company": "string", "duration": "string"}],
            "education": [{"degree": "string", "institution": "string", "year": "string"}],
            "certifications": ["string"],
        },
        "scores": {
            "skill_match_score": "number 0..100",
            "experience_match_score": "number 0..100",
            "education_match_score": "number 0..100",
        },
        "analysis": {
            "matched_skills": ["string"],
            "missing_skills": ["string"],
            "skill_rationale": "1-2 concise sentences",
            "experience_rationale": "1-2 concise sentences",
            "education_rationale": "1-2 concise sentences",
            "strengths": ["2-4 concise strengths"],
            "concerns": ["1-3 concise gaps or risks"],
            "ai_summary": "2-3 sentence executive summary for HR",
        },
    }

    user_prompt = (
        f"JOB REQUIREMENTS:\n"
        f"- Title: {job.title}\n"
        f"- Department / Category: {job.department} / {job.job_category}\n"
        f"- City / Work Mode: {job.city} / {job.work_mode}\n"
        f"- Required Experience: {exp_range} (Fresh graduate eligible: {'Yes' if job.fresh_graduate_eligible else 'No'})\n"
        f"- Minimum Education: {job.min_education_level}\n"
        f"- Required Skills: {', '.join(job.required_skills or []) or 'None'}\n"
        f"- Programming Languages: {', '.join(job.programming_languages or []) or 'None'}\n"
        f"- Frameworks / Libraries: {', '.join(job.frameworks or []) or 'None'}\n"
        f"- Tools: {', '.join(job.tools or []) or 'None'}\n"
        f"- Cloud Platforms: {', '.join(job.cloud_platforms or []) or 'None'}\n"
        f"- Technical Knowledge Notes: {job.technical_knowledge or 'None'}\n"
        f"- Key Responsibilities: {'; '.join(responsibilities) or 'See JD below'}\n"
        f"- Job Description Excerpt:\n{jd_excerpt}\n\n"
        f"HR CANDIDATE HINTS (if provided): {json.dumps(hints)}\n\n"
        f"REQUIRED JSON OUTPUT SHAPE:\n{json.dumps(schema_instructions)}\n\n"
        f"CANDIDATE CV TEXT:\n{raw_text[:14000]}"
    )

    try:
        raw_reply = call_groq_chat(system, user_prompt, temperature=0.2, max_tokens=2400, json_mode=True)
    except RuntimeError as exc:
        if "response_format" in str(exc).lower():
            raw_reply = call_groq_chat(system, user_prompt, temperature=0.2, max_tokens=2400, json_mode=False)
        else:
            raise
    return _parse_json_response(raw_reply)


def compute_weighted_evaluation(
    job: JobPosting,
    skill_score: Decimal | float | int,
    exp_score: Decimal | float | int,
    edu_score: Decimal | float | int,
    existing_breakdown: dict | None = None,
) -> tuple[Decimal, dict]:
    """Compute weighted CV overall_score (0..100) and structured breakdown deterministically."""
    s_val = _quantize_2(skill_score)
    e_val = _quantize_2(exp_score)
    ed_val = _quantize_2(edu_score)

    w_skill = int(job.cv_skill_weight)
    w_exp = int(job.cv_experience_weight)
    w_edu = int(job.cv_education_weight)
    min_pass = int(job.cv_min_passing_score)

    c_skill = (s_val * Decimal(w_skill) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    c_exp = (e_val * Decimal(w_exp) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    c_edu = (ed_val * Decimal(w_edu) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    overall = min(Decimal("100.00"), (c_skill + c_exp + c_edu).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    breakdown = dict(existing_breakdown or {})
    breakdown.update(
        {
            "weights": {
                "skills": w_skill,
                "experience": w_exp,
                "education": w_edu,
            },
            "weighted_contributions": {
                "skills": float(c_skill),
                "experience": float(c_exp),
                "education": float(c_edu),
            },
            "min_passing_score": min_pass,
            "meets_threshold": float(overall) >= float(min_pass),
        }
    )
    return overall, breakdown


def refresh_job_shortlist(job: JobPosting) -> None:
    """Rank evaluated applicants for a job and mark eligible top-N as shortlisted."""
    evaluations = list(
        CvEvaluation.objects.select_related("application")
        .filter(application__job_posting=job)
        .order_by("-overall_score", "-skill_match_score", "evaluated_at")
    )
    cutoff = Decimal(str(job.cv_min_passing_score))
    cap = int(job.shortlist_after_cv_count or 25)
    shortlisted_slots = 0
    now = timezone.now()

    for ev in evaluations:
        app = ev.application
        breakdown = ev.match_breakdown if isinstance(ev.match_breakdown, dict) else {}
        hr_decision = breakdown.get("hr_decision")

        if app.status not in PRE_INTERVIEW_STATUSES and app.status != "rejected":
            # Candidate already moved into interview/final stages.
            if ev.is_shortlisted:
                shortlisted_slots += 1
            continue

        if hr_decision == "shortlisted":
            new_shortlisted = True
            new_status = "shortlisted"
            shortlisted_slots += 1
        elif hr_decision == "rejected":
            new_shortlisted = False
            new_status = "rejected"
        else:
            eligible = ev.overall_score >= cutoff and shortlisted_slots < cap
            if eligible:
                shortlisted_slots += 1
                new_shortlisted = True
                new_status = "shortlisted"
            else:
                new_shortlisted = False
                new_status = "screened"

        if ev.is_shortlisted != new_shortlisted:
            ev.is_shortlisted = new_shortlisted
            ev.save(update_fields=["is_shortlisted"])
        if app.status != new_status:
            app.status = new_status
            app.updated_at = now
            app.save(update_fields=["status", "updated_at"])


@transaction.atomic
def recalculate_job_cv_scores(job: JobPosting) -> int:
    """Recompute weighted overall_score and pass status after HR edits CV weights/cutoff."""
    evaluations = list(
        CvEvaluation.objects.select_related("application").filter(application__job_posting=job)
    )
    for ev in evaluations:
        overall, breakdown = compute_weighted_evaluation(
            job,
            ev.skill_match_score,
            ev.experience_match_score,
            ev.education_match_score,
            existing_breakdown=ev.match_breakdown if isinstance(ev.match_breakdown, dict) else {},
        )
        ev.overall_score = overall
        ev.match_breakdown = breakdown
        ev.save(update_fields=["overall_score", "match_breakdown"])
    refresh_job_shortlist(job)
    return len(evaluations)


@transaction.atomic
def score_candidate_cv_for_job(
    job: JobPosting,
    *,
    uploaded_file=None,
    resume_text: str = "",
    full_name: str = "",
    email: str = "",
    phone: str = "",
    location: str = "",
    source: str = "manual_upload",
    source_message_id: str = "",
) -> Application:
    """Parse CV, evaluate with Groq against job rubric, compute weighted score, and persist."""
    raw_text, raw_bytes, orig_filename, mime_type = extract_resume_content(
        uploaded_file=uploaded_file,
        pasted_text=resume_text,
    )
    hints = {
        "full_name": (full_name or "").strip(),
        "email": (email or "").strip(),
        "phone": (phone or "").strip(),
        "location": (location or "").strip(),
    }

    ai_result = _score_cv_with_groq(job, raw_text, hints=hints)
    cand_block = ai_result.get("candidate") if isinstance(ai_result.get("candidate"), dict) else {}
    parsed_block = ai_result.get("parsed_cv") if isinstance(ai_result.get("parsed_cv"), dict) else {}
    scores_block = ai_result.get("scores") if isinstance(ai_result.get("scores"), dict) else {}
    analysis_block = ai_result.get("analysis") if isinstance(ai_result.get("analysis"), dict) else {}

    resolved_email = (email or cand_block.get("email") or "").strip().lower()
    if not resolved_email or "@" not in resolved_email:
        # Try regex fallback in raw text before failing cleanly.
        m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw_text)
        resolved_email = m.group(0).lower() if m else ""
    if not resolved_email:
        raise ValueError("Candidate email could not be detected from the CV. Please enter their email.")

    resolved_name = (full_name or cand_block.get("full_name") or "").strip()[:200]
    if not resolved_name:
        resolved_name = resolved_email.split("@", 1)[0].replace(".", " ").title()[:200]

    resolved_phone = (phone or cand_block.get("phone") or "").strip()[:50] or None
    resolved_location = (location or cand_block.get("location") or "").strip()[:150] or None
    resolved_linkedin = (cand_block.get("linkedin_url") or "").strip()[:300] or None

    now = timezone.now()
    resume_url = _save_resume_blob(job.id, orig_filename, raw_bytes)

    candidate = Candidate.objects.filter(email=resolved_email).first()
    if candidate is None:
        candidate = Candidate.objects.create(
            email=resolved_email,
            full_name=resolved_name,
            phone=resolved_phone,
            linkedin_url=resolved_linkedin,
            location=resolved_location,
            created_at=now,
            updated_at=now,
        )
    else:
        changed = False
        if full_name.strip() or not candidate.full_name:
            candidate.full_name = resolved_name
            changed = True
        if resolved_phone and not candidate.phone:
            candidate.phone = resolved_phone
            changed = True
        if resolved_location and not candidate.location:
            candidate.location = resolved_location
            changed = True
        if resolved_linkedin and not candidate.linkedin_url:
            candidate.linkedin_url = resolved_linkedin
            changed = True
        if changed:
            candidate.updated_at = now
            candidate.save()

    app = Application.objects.filter(job_posting=job, candidate=candidate).first()
    if app is None:
        app = Application.objects.create(
            job_posting=job,
            candidate=candidate,
            source=source,
            source_message_id=source_message_id or None,
            resume_file_url=resume_url,
            resume_original_filename=orig_filename,
            resume_mime_type=mime_type,
            status="screened",
            created_at=now,
            updated_at=now,
        )
    else:
        app.source = source
        if source_message_id:
            app.source_message_id = source_message_id
        app.resume_file_url = resume_url
        app.resume_original_filename = orig_filename
        app.resume_mime_type = mime_type
        if app.status in {"applied", "parsing_cv", "rejected"}:
            app.status = "screened"
        app.updated_at = now
        app.save()

    structured_profile = {
        "experience_summary": str(parsed_block.get("experience_summary") or "").strip(),
        "education_summary": str(parsed_block.get("education_summary") or "").strip(),
        "work_history": parsed_block.get("work_history") if isinstance(parsed_block.get("work_history"), list) else [],
        "education": parsed_block.get("education") if isinstance(parsed_block.get("education"), list) else [],
        "certifications": _clean_string_list(parsed_block.get("certifications"), limit=15),
    }
    extracted_skills = _clean_string_list(parsed_block.get("extracted_skills"), limit=35)
    exp_years = _quantize_exp_years(parsed_block.get("experience_years"))
    highest_degree = str(parsed_block.get("highest_degree") or "").strip()[:150] or None

    ParsedCv.objects.update_or_create(
        application=app,
        defaults={
            "raw_text": raw_text,
            "structured_profile": structured_profile,
            "extracted_skills": extracted_skills,
            "extracted_experience_years": exp_years,
            "highest_degree": highest_degree,
            "parsing_model": groq_model_name()[:100],
            "parsed_at": now,
        },
    )

    skill_score = _quantize_2(scores_block.get("skill_match_score", 0))
    exp_score = _quantize_2(scores_block.get("experience_match_score", 0))
    edu_score = _quantize_2(scores_block.get("education_match_score", 0))

    breakdown_extra = {
        "matched_skills": _clean_string_list(analysis_block.get("matched_skills"), limit=25),
        "missing_skills": _clean_string_list(analysis_block.get("missing_skills"), limit=25),
        "rationales": {
            "skills": str(analysis_block.get("skill_rationale") or "").strip(),
            "experience": str(analysis_block.get("experience_rationale") or "").strip(),
            "education": str(analysis_block.get("education_rationale") or "").strip(),
        },
        "hr_decision": None,
    }
    overall_score, breakdown = compute_weighted_evaluation(
        job,
        skill_score,
        exp_score,
        edu_score,
        existing_breakdown=breakdown_extra,
    )

    strengths = _clean_string_list(analysis_block.get("strengths"), limit=6, item_max=240)
    concerns = _clean_string_list(analysis_block.get("concerns"), limit=6, item_max=240)
    ai_summary = str(analysis_block.get("ai_summary") or "").strip() or "CV evaluated against job requirements."

    CvEvaluation.objects.update_or_create(
        application=app,
        defaults={
            "overall_score": overall_score,
            "skill_match_score": skill_score,
            "experience_match_score": exp_score,
            "education_match_score": edu_score,
            "match_breakdown": breakdown,
            "ai_summary": ai_summary,
            "strengths": strengths,
            "concerns": concerns,
            "is_shortlisted": False,
            "evaluated_at": now,
        },
    )

    refresh_job_shortlist(job)
    return Application.objects.select_related(
        "candidate", "job_posting", "parsed_cv", "cv_evaluation"
    ).get(id=app.id)


@transaction.atomic
def apply_manual_decision(application: Application, decision: str) -> Application:
    """Allow HR to override CV shortlist/reject status cleanly."""
    if decision not in {"shortlisted", "rejected", "auto"}:
        raise ValueError("Decision must be shortlisted, rejected, or auto.")
    ev = CvEvaluation.objects.filter(application=application).first()
    if ev:
        breakdown = dict(ev.match_breakdown or {})
        breakdown["hr_decision"] = None if decision == "auto" else decision
        ev.match_breakdown = breakdown
        ev.save(update_fields=["match_breakdown"])
    if decision in {"shortlisted", "rejected"}:
        application.status = decision
        application.updated_at = timezone.now()
        application.save(update_fields=["status", "updated_at"])
    refresh_job_shortlist(application.job_posting)
    return Application.objects.select_related(
        "candidate", "job_posting", "parsed_cv", "cv_evaluation"
    ).get(id=application.id)


def serialize_application(app: Application) -> dict:
    """Build template/JSON scorecard payload for one evaluated application."""
    cand = app.candidate
    job = app.job_posting
    parsed = getattr(app, "parsed_cv", None)
    ev = getattr(app, "cv_evaluation", None)

    parts = (cand.full_name or "").split()
    initials = "".join(p[0].upper() for p in parts[:2] if p) or "CV"

    profile = (parsed.structured_profile if parsed and isinstance(parsed.structured_profile, dict) else {})
    exp_years_str = (
        f"{parsed.extracted_experience_years} yrs"
        if parsed and parsed.extracted_experience_years is not None
        else None
    )
    experience_text = profile.get("experience_summary") or exp_years_str or "Experience details extracted in resume."
    education_text = profile.get("education_summary") or (parsed.highest_degree if parsed else None) or "—"

    breakdown = (ev.match_breakdown if ev and isinstance(ev.match_breakdown, dict) else {})
    weights = breakdown.get("weights") or {
        "skills": job.cv_skill_weight,
        "experience": job.cv_experience_weight,
        "education": job.cv_education_weight,
    }
    contributions = breakdown.get("weighted_contributions") or {"skills": 0, "experience": 0, "education": 0}
    rationales = breakdown.get("rationales") or {}
    min_pass = int(breakdown.get("min_passing_score", job.cv_min_passing_score))
    overall = float(ev.overall_score) if ev else 0.0
    meets_threshold = bool(breakdown.get("meets_threshold", overall >= min_pass))

    ui_status = "screened"
    if app.status == "shortlisted" or (ev and ev.is_shortlisted and app.status != "rejected"):
        ui_status = "shortlisted"
    elif app.status == "rejected":
        ui_status = "rejected"
    elif app.status in {"interview_invited", "interview_scheduled", "interview_in_progress", "interview_completed"}:
        ui_status = "interviewing"

    return {
        "id": str(app.id),
        "job_id": str(job.id),
        "initials": initials,
        "name": cand.full_name,
        "email": cand.email,
        "phone": cand.phone or "",
        "role": job.title,
        "city": cand.location or job.city,
        "applied": app.created_at.strftime("%d %b %Y") if app.created_at else "",
        "status": ui_status,
        "raw_status": app.status,
        "is_shortlisted": bool(ev.is_shortlisted) if ev else False,
        "score": round(overall),
        "overall_score": round(overall, 1),
        "skills_score": round(float(ev.skill_match_score)) if ev else 0,
        "exp_score": round(float(ev.experience_match_score)) if ev else 0,
        "edu_score": round(float(ev.education_match_score)) if ev else 0,
        "weights": weights,
        "weighted_contributions": contributions,
        "min_passing_score": min_pass,
        "meets_threshold": meets_threshold,
        "matched_skills": breakdown.get("matched_skills") or [],
        "missing_skills": breakdown.get("missing_skills") or [],
        "rationales": {
            "skills": rationales.get("skills") or "",
            "experience": rationales.get("experience") or "",
            "education": rationales.get("education") or "",
        },
        "hr_decision": breakdown.get("hr_decision"),
        "experience": experience_text,
        "education": education_text,
        "experience_years": str(parsed.extracted_experience_years) if parsed and parsed.extracted_experience_years is not None else "—",
        "highest_degree": (parsed.highest_degree if parsed else None) or "—",
        "skills": (parsed.extracted_skills if parsed else []) or [],
        "insight": ev.ai_summary if ev else "Pending evaluation.",
        "strengths": ev.strengths if ev else [],
        "concerns": ev.concerns if ev else [],
        "resume_file_url": app.resume_file_url,
        "resume_original_filename": app.resume_original_filename,
    }


def applications_for_company(company) -> list[dict]:
    """Return all evaluated/received applications for a company sorted by score."""
    qs = (
        Application.objects.select_related("candidate", "job_posting", "parsed_cv", "cv_evaluation")
        .filter(job_posting__company=company)
        .order_by("-cv_evaluation__overall_score", "-created_at")
    )
    return [serialize_application(app) for app in qs]

