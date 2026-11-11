"""End-to-end verification for CV scoring metrics, parsers, APIs, and live Groq evaluation."""

import io
import json
import os
import shutil
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.utils import timezone
from docx import Document
from pypdf import PdfWriter

from portal.account_deletion import purge_user_account
from portal.auth_user import HrAuthUser
from portal.cv_scoring_service import _score_cv_with_groq, compute_weighted_evaluation, extract_resume_content
from portal.forms import JobIntakeForm
from portal.models import Application, Candidate, Company, CvEvaluation, JobPosting, ParsedCv, User
from portal.services import create_job_posting


def _make_sample_docx_bytes(text_lines: list[str]) -> bytes:
    doc = Document()
    for line in text_lines:
        doc.add_paragraph(line)
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Core Stack"
    table.cell(0, 1).text = "Python, Django, PostgreSQL, Docker"
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def main():
    # 1. Verify DB columns and constraints exist
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'job_postings'
              AND column_name IN ('cv_skill_weight', 'cv_experience_weight', 'cv_education_weight', 'cv_min_passing_score')
            """
        )
        cols = {r[0] for r in cur.fetchall()}
        assert cols == {
            "cv_skill_weight",
            "cv_experience_weight",
            "cv_education_weight",
            "cv_min_passing_score",
        }, f"Missing DB columns: {cols}"

    # 2. Verify JobIntakeForm validates weights totaling 100
    base_post = {
        "title": "Senior Backend Engineer",
        "department": "engineering",
        "job_category": "software_development",
        "employment_type": "full_time",
        "work_mode": "hybrid",
        "urgency_level": "normal",
        "city": "Lahore",
        "target_hires": "2",
        "job_description": "Build scalable Python/Django recruitment APIs and PostgreSQL data pipelines.",
        "company_name": "VerifyCV Co",
        "posting_date": str(timezone.localdate()),
        "application_deadline": str(timezone.localdate()),
        "min_experience_years": "3",
        "max_experience_years": "6",
        "fresh_graduate_eligible": "no",
        "min_education_level": "bachelors",
        "required_skills_csv": "Python, Django, PostgreSQL",
        "programming_languages_csv": "Python, SQL",
        "frameworks_csv": "Django",
        "tools_csv": "Git, Docker",
        "cloud_platforms_csv": "AWS",
        "technical_knowledge": "REST APIs, relational DB optimization",
        "salary_period": "per_month",
        "job_post_tone": "professional",
        "cv_skill_weight": "50",
        "cv_experience_weight": "30",
        "cv_education_weight": "20",
        "cv_min_passing_score": "75",
        "shortlist_after_cv_count": "25",
        "shortlist_after_interview_count": "10",
        "key_responsibilities": ["Design REST services", "Optimize SQL queries"],
    }

    bad_post = dict(base_post, cv_skill_weight="40", cv_experience_weight="40", cv_education_weight="10")
    from django.http import QueryDict

    def _to_qd(d):
        qd = QueryDict("", mutable=True)
        for k, v in d.items():
            if isinstance(v, list):
                for item in v:
                    qd.appendlist(k, item)
            else:
                qd[k] = v
        return qd

    bad_form = JobIntakeForm(_to_qd(bad_post), company_name="VerifyCV Co")
    bad_form.expected_company_name = "VerifyCV Co"
    assert not bad_form.is_valid(), "Expected weight sum 90 to fail validation"
    assert "cv_skill_weight" in bad_form.errors

    good_form = JobIntakeForm(_to_qd(base_post), company_name="VerifyCV Co")
    good_form.expected_company_name = "VerifyCV Co"
    assert good_form.is_valid(), f"Form errors: {good_form.errors}"

    now = timezone.now()
    uid = uuid.uuid4().hex[:8]
    company = Company.objects.create(name="VerifyCV Co", city="Lahore")
    user = User.objects.create(
        company=company,
        email=f"hr.cvtest.{uid}@example.com",
        full_name="CV Test HR",
        password_hash="!google-oauth-only",
        profile_complete=True,
        created_at=now,
        updated_at=now,
    )
    job = None
    candidate_email = f"cand.{uid}@example.com"

    try:
        job = create_job_posting(company, user, good_form.cleaned_data)
        assert (job.cv_skill_weight, job.cv_experience_weight, job.cv_education_weight, job.cv_min_passing_score) == (
            50,
            30,
            20,
            75,
        )

        # Deterministic weight calculation check
        overall, breakdown = compute_weighted_evaluation(job, 80, 70, 90)
        assert overall == Decimal("79.00"), f"Expected 79.00, got {overall}"
        assert breakdown["meets_threshold"] is True

        # HTTP endpoint tests via authenticated Django Client
        client = Client()
        client.force_login(HrAuthUser(user), backend="portal.auth_backend.HrSessionBackend")

        # Test dashboard renders new CV Scoring Metrics UI cleanly
        dash_res = client.get("/dashboard/")
        assert dash_res.status_code == 200
        html = dash_res.content.decode("utf-8")
        assert "CV Scoring Metrics" in html
        assert "cv-jobs-data" in html
        assert "cv_scoring.js" in html

        # Upload & score a real DOCX file (mock Groq so weighted math is deterministic)
        docx_bytes = _make_sample_docx_bytes(
            [
                f"Ayesha Khan | {candidate_email} | Lahore, Pakistan",
                "Senior Python Developer with 4 years building Django REST APIs and PostgreSQL backends.",
                "Education: BS Computer Science, FAST-NUCES Lahore (2021).",
            ]
        )
        uploaded = SimpleUploadedFile(
            "ayesha_cv.docx",
            docx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        mock_ai_payload = {
            "candidate": {
                "full_name": "Ayesha Khan",
                "email": candidate_email,
                "phone": "+92 300 1234567",
                "location": "Lahore",
                "linkedin_url": "",
            },
            "parsed_cv": {
                "highest_degree": "BS Computer Science",
                "experience_years": 4,
                "extracted_skills": ["Python", "Django", "PostgreSQL", "Docker"],
                "experience_summary": "4 years building Django REST APIs and PostgreSQL systems.",
                "education_summary": "BS Computer Science from FAST-NUCES Lahore.",
                "work_history": [],
                "education": [],
                "certifications": [],
            },
            "scores": {
                "skill_match_score": 80,
                "experience_match_score": 70,
                "education_match_score": 90,
            },
            "analysis": {
                "matched_skills": ["Python", "Django", "PostgreSQL", "Docker"],
                "missing_skills": ["AWS"],
                "skill_rationale": "Strong backend Python, Django, PostgreSQL, and Docker match; missing AWS.",
                "experience_rationale": "4 years meets the 3–6 year requirement directly.",
                "education_rationale": "BS Computer Science exceeds Bachelor minimum.",
                "strengths": ["Strong Django & PostgreSQL depth", "4 years relevant experience"],
                "concerns": ["No explicit AWS deployment listed"],
                "ai_summary": "Strong backend match meeting skills, experience, and degree requirements.",
            },
        }

        with patch("portal.cv_scoring_service._score_cv_with_groq", return_value=mock_ai_payload):
            score_res = client.post(
                "/dashboard/applications/score-cv/",
                {"job_id": str(job.id), "resume_file": uploaded},
            )
        assert score_res.status_code == 200, score_res.content
        sdata = score_res.json()
        assert sdata["ok"] is True
        app_id = sdata["application"]["id"]
        assert sdata["application"]["overall_score"] == 79.0
        assert sdata["application"]["status"] == "shortlisted"
        assert sdata["application"]["meets_threshold"] is True

        # Update weights to Experience-heavy (20/60/20) and cutoff 78% -> overall becomes 0.2*80 + 0.6*70 + 0.2*90 = 76.0 (below 78%)
        metrics_res = client.post(
            f"/dashboard/jobs/{job.id}/cv-metrics/",
            data=json.dumps(
                {
                    "cv_skill_weight": 20,
                    "cv_experience_weight": 60,
                    "cv_education_weight": 20,
                    "cv_min_passing_score": 78,
                }
            ),
            content_type="application/json",
        )
        assert metrics_res.status_code == 200, metrics_res.content
        mdata = metrics_res.json()
        assert mdata["ok"] is True
        updated_cand = next(c for c in mdata["candidates"] if c["id"] == app_id)
        assert updated_cand["overall_score"] == 76.0, f"Expected 76.0, got {updated_cand['overall_score']}"
        assert updated_cand["meets_threshold"] is False
        assert updated_cand["status"] == "screened"

        # Manual override to shortlisted
        dec_res = client.post(
            f"/dashboard/applications/{app_id}/decision/",
            data=json.dumps({"decision": "shortlisted"}),
            content_type="application/json",
        )
        assert dec_res.status_code == 200, dec_res.content
        assert dec_res.json()["application"]["status"] == "shortlisted"

        # Validate blank/scanned PDF guard & pasted text extraction
        blank_pdf = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.write(blank_pdf)
        try:
            extract_resume_content(
                uploaded_file=SimpleUploadedFile("scan.pdf", blank_pdf.getvalue(), content_type="application/pdf")
            )
            raise AssertionError("Blank PDF should fail readable text extraction check")
        except ValueError as exc:
            assert "readable text" in str(exc).lower()

        pasted_res, _, pasted_name, pasted_mime = extract_resume_content(
            pasted_text="Senior Python Engineer with 5 years Django, PostgreSQL, Docker, AWS."
        )
        assert "Python" in pasted_res and pasted_name == "pasted_cv.txt" and pasted_mime == "text/plain"

        if "--live-groq" in sys.argv:
            live_ai = _score_cv_with_groq(
                job,
                "Bilal Ahmed, email bilal@example.pk, 5 years Python Django PostgreSQL AWS experience, BS CS LUMS.",
            )
            assert "scores" in live_ai and "skill_match_score" in live_ai["scores"]
            print("OK: Live Groq returned scores:", live_ai["scores"])

        print("OK: All deterministic CV scoring tests passed (DB, Form, Extractors, APIs, Recalc, Shortlist).")
    finally:
        if job is not None:
            media_dir = Path(settings.MEDIA_ROOT) / "resumes" / str(job.id)
            if media_dir.exists():
                shutil.rmtree(media_dir, ignore_errors=True)
        Candidate.objects.filter(email=candidate_email).delete()
        purge_user_account(user)


if __name__ == "__main__":
    main()
