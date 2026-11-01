import os
import re

from django.utils import timezone
from groq import Groq

from .choices import (
    DEPARTMENTS,
    EDUCATION_LEVELS,
    EMPLOYMENT_TYPES,
    JOB_CATEGORIES,
    JOB_POST_TONES,
    SALARY_PERIODS,
    URGENCY_LEVELS,
    WORK_MODES,
)

_LABEL = {
    **dict(DEPARTMENTS),
    **dict(JOB_CATEGORIES),
    **dict(EMPLOYMENT_TYPES),
    **dict(WORK_MODES),
    **dict(URGENCY_LEVELS),
    **dict(EDUCATION_LEVELS),
    **dict(SALARY_PERIODS),
    **dict(JOB_POST_TONES),
}


def _label(key: str, value: str) -> str:
    if not value:
        return ""
    return _LABEL.get(value, value.replace("_", " ").title())


def _list_section(title: str, items: list[str]) -> str:
    if not items:
        return ""
    lines = [f"{title}:"] + [f"- {item}" for item in items]
    return "\n".join(lines)


def build_prompt_payload(job) -> dict:
    """Structured facts sent to the model (also stored on the job row)."""
    company = job.company
    key_resp = [
        r.body
        for r in job.responsibilities.filter(kind="key_responsibility").order_by("sort_order")
    ]
    daily = [
        r.body for r in job.responsibilities.filter(kind="daily_task").order_by("sort_order")
    ]

    benefits = []
    if job.salary_negotiable:
        benefits.append("Salary negotiable")
    if job.performance_bonus:
        benefits.append("Performance bonus")
    if job.commission_incentives:
        benefits.append("Commission / incentives")
    if job.health_insurance:
        benefits.append("Health insurance")
    if job.provident_fund:
        benefits.append("Provident fund / retirement benefits")
    if job.relocation_assistance:
        benefits.append("Relocation assistance")
    if job.equipment_provided:
        benefits.append("Equipment provided")
    if job.paid_leave_policy:
        benefits.append(f"Paid leave: {job.paid_leave_policy}")
    if job.other_benefits:
        benefits.append(f"Other benefits: {job.other_benefits}")

    salary_bits = []
    if job.min_salary is not None or job.max_salary is not None:
        lo = f"{int(job.min_salary):,}" if job.min_salary is not None else None
        hi = f"{int(job.max_salary):,}" if job.max_salary is not None else None
        period = _label("", job.salary_period)
        if lo and hi:
            salary_bits.append(f"PKR {lo} – {hi} ({period})")
        elif lo:
            salary_bits.append(f"From PKR {lo} ({period})")
        elif hi:
            salary_bits.append(f"Up to PKR {hi} ({period})")
    else:
        salary_bits.append("Not disclosed in posting")

    tone_label = _label("", job.job_post_tone)
    exp = f"{job.min_experience_years}+ years"
    if job.max_experience_years is not None:
        exp = f"{job.min_experience_years}–{job.max_experience_years} years"

    return {
        "company_name": company.name,
        "company_city": company.city or job.city,
        "company_industry": company.industry or "",
        "title": job.title,
        "department": _label("", job.department),
        "category": _label("", job.job_category),
        "employment_type": _label("", job.employment_type),
        "work_mode": _label("", job.work_mode),
        "urgency": _label("", job.urgency_level),
        "location_city": job.city,
        "vacancies": job.target_hires,
        "posting_date": str(job.posting_date),
        "application_deadline": str(job.application_deadline),
        "hr_baseline_description": job.job_description,
        "experience": exp,
        "fresh_graduate_eligible": "Yes" if job.fresh_graduate_eligible else "No",
        "min_education": _label("", job.min_education_level),
        "required_skills": job.required_skills or [],
        "programming_languages": job.programming_languages or [],
        "frameworks": job.frameworks or [],
        "tools": job.tools or [],
        "cloud_platforms": job.cloud_platforms or [],
        "technical_knowledge": job.technical_knowledge or "",
        "salary_summary": "; ".join(salary_bits),
        "benefits": benefits,
        "key_responsibilities": key_resp,
        "daily_tasks": daily,
        "tone": tone_label,
        "custom_tone_instructions": job.custom_tone_instructions or "",
        "shortlist_after_cv": job.shortlist_after_cv_count,
        "shortlist_after_interview": job.shortlist_after_interview_count,
    }


def _system_prompt() -> str:
    return (
        "You are an expert HR copywriter for Pakistani technology and corporate employers. "
        "Write complete, publish-ready job descriptions that are clear, inclusive, and accurate. "
        "Use the facts provided only; do not invent employers, locations, or benefits that were not given. "
        "Formatting rules (strict): "
        "Do NOT use markdown symbols—no #, ##, **, __, backticks, or hyphen bullets (-). "
        "Section titles must be on their own line in Title Case (example: About the Company). "
        "Use the bullet character • followed by a space for list items. "
        "Output plain text only (no JSON, no code fences). "
        "Always end with a section titled How to Apply containing exactly this line and nothing after the colon: "
        "Apply Here: "
        "(leave blank after the colon; do not invent URLs or email addresses)."
    )


def _user_prompt(facts: dict) -> str:
    tone = facts["tone"]
    extra_tone = facts.get("custom_tone_instructions") or ""
    tone_line = f"Writing tone: {tone}."
    if extra_tone:
        tone_line += f" Custom tone notes: {extra_tone}"

    sections = [
        f"Company: {facts['company_name']} ({facts.get('company_city', '')}, Pakistan).",
        f"Role: {facts['title']} — {facts['department']} / {facts['category']}.",
        f"Employment: {facts['employment_type']}, {facts['work_mode']}. Urgency: {facts['urgency']}.",
        f"Location: {facts['location_city']}. Vacancies: {facts['vacancies']}.",
        f"Dates: posting {facts['posting_date']}, apply by {facts['application_deadline']}.",
        tone_line,
        f"Experience: {facts['experience']}. Fresh graduates: {facts['fresh_graduate_eligible']}.",
        f"Minimum education: {facts['min_education']}.",
        _list_section("Required skills", facts["required_skills"]),
        _list_section("Programming languages", facts["programming_languages"]),
        _list_section("Frameworks / libraries", facts["frameworks"]),
        _list_section("Tools", facts["tools"]),
        _list_section("Cloud platforms", facts["cloud_platforms"]),
        f"Technical knowledge notes: {facts['technical_knowledge'] or 'None provided.'}",
        _list_section("Key responsibilities", facts["key_responsibilities"]),
        _list_section("Daily tasks", facts["daily_tasks"]),
        f"Salary: {facts['salary_summary']}.",
        _list_section("Benefits", facts["benefits"]),
        f"HR baseline notes to refine (not necessarily final copy):\n{facts['hr_baseline_description']}",
        (
            "Write a full job description suitable for Rozee.pk / LinkedIn. "
            "Include sections: About the Company, Role Overview, Key Responsibilities, "
            "Requirements, Benefits and Compensation (respect salary disclosure), and Equal Opportunity statement. "
            "Close with section How to Apply and the single line: Apply Here: (empty after colon)."
        ),
    ]
    return "\n\n".join(s for s in sections if s.strip())


def call_groq_chat(system: str, user: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in Frontend/.env")

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.55,
            max_tokens=4096,
        )
    except Exception as exc:
        msg = str(exc)
        if "invalid_api_key" in msg.lower() or "401" in msg:
            raise RuntimeError(
                "Groq rejected the API key. Open console.groq.com, create a new key, "
                "and update GROQ_API_KEY in Frontend/.env, then restart runserver."
            ) from exc
        raise RuntimeError(f"Groq API error: {msg[:500]}") from exc

    choices = response.choices or []
    if not choices:
        raise RuntimeError("Groq returned no choices")
    content = (choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Groq returned empty content")
    return content


def normalize_job_description_output(text: str) -> str:
    """Ensure apply footer exists and strip common markdown artifacts."""
    cleaned = text.strip()
    lines = []
    for raw in cleaned.splitlines():
        line = raw.rstrip()
        stripped = line.lstrip()
        if stripped.startswith("#"):
            stripped = re.sub(r"^#+\s*", "", stripped)
        stripped = re.sub(r"^\*\*(.+)\*\*$", r"\1", stripped)
        stripped = re.sub(r"^[-*]\s+", "• ", stripped)
        lines.append(stripped)
    cleaned = "\n".join(lines).strip()

    if "Apply Here:" not in cleaned:
        cleaned += "\n\nHow to Apply\nApply Here: \n"
    elif not re.search(r"Apply Here:\s*$", cleaned, re.MULTILINE | re.IGNORECASE):
        cleaned = re.sub(
            r"(Apply Here:\s*)(\S.*)?$",
            r"\1",
            cleaned,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    return cleaned


def generate_job_description_text(job) -> tuple[str, dict]:
    facts = build_prompt_payload(job)
    system = _system_prompt()
    user = _user_prompt(facts)
    text = normalize_job_description_output(call_groq_chat(system, user))
    meta = {
        "generated_at": timezone.now().isoformat(),
        "model": os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
        "facts": facts,
    }
    return text, meta
