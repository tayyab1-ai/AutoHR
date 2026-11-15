"""Automated verification suite for Google Form responses automated sync worker."""

import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import django

django.setup()

from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from portal.cv_views import sync_all_forms_api, sync_job_form_api
from portal.google_form_sync_service import (
    _build_cv_text_from_answers,
    _match_question_key,
    sync_all_active_forms,
    sync_job_form_responses,
)
from portal.models import Application, Candidate, Company, JobPosting, User
from portal.profile_models import JobApplicationFormConfig, OAuthCredential


class TestGoogleFormSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = timezone.now()
        cls.company, _ = Company.objects.get_or_create(
            name="Test Sync Corp",
            defaults={"city": "Lahore", "country": "Pakistan"},
        )
        cls.user, _ = User.objects.get_or_create(
            email="hr_sync_test@autohr.internal",
            defaults={
                "company": cls.company,
                "full_name": "Sync Test HR",
                "password_hash": "dummy",
                "role": "hr_manager",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.job, _ = JobPosting.objects.get_or_create(
            company=cls.company,
            title="Senior Python Cloud Engineer",
            defaults={
                "created_by": cls.user,
                "department": "Engineering",
                "job_category": "Software",
                "employment_type": "Full-time",
                "work_mode": "Hybrid",
                "city": "Lahore",
                "target_hires": 1,
                "job_description": "We need a Senior Python engineer experienced in Django, Postgres, and Docker.",
                "posting_date": now.date(),
                "application_deadline": (now + timezone.timedelta(days=14)).date(),
                "min_experience_years": 4,
                "min_education_level": "Bachelor's",
                "required_skills": ["Python", "Django", "PostgreSQL", "Docker"],
                "job_post_tone": "Professional",
                "cv_skill_weight": 50,
                "cv_experience_weight": 30,
                "cv_education_weight": 20,
                "cv_min_passing_score": 60,
                "shortlist_after_cv_count": 25,
                "status": "approved",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.config, _ = JobApplicationFormConfig.objects.get_or_create(
            job_id=cls.job.id,
            defaults={
                "company_id": cls.company.id,
                "application_form_title": "Senior Python Cloud Engineer - Application",
                "google_form_id": "mock_google_form_12345",
                "google_form_url": "https://docs.google.com/forms/d/mock_google_form_12345/viewform",
                "status": "active",
            },
        )

    def test_01_question_key_matching(self):
        self.assertEqual(_match_question_key("Full Name"), "full_name")
        self.assertEqual(_match_question_key("Email Address"), "email")
        self.assertEqual(_match_question_key("Total Professional Experience (Years)"), "total_experience_years")
        self.assertEqual(_match_question_key("Primary Technical Skills"), "primary_skills")
        self.assertEqual(_match_question_key("Highest Education Level"), "education_level")

    def test_02_synthetic_cv_synthesis(self):
        answers = {
            "full_name": "Fatima Zahra",
            "email": "fatima.zahra@example.com",
            "phone": "+92-300-1122334",
            "current_city": "Islamabad",
            "country": "Pakistan",
            "degree": "BS Software Engineering",
            "university": "NUST",
            "graduation_year": "2020",
            "total_experience_years": "5",
            "current_company": "Tech Innovations",
            "current_job_title": "Senior Backend Developer",
            "primary_skills": "Python, Django, FastAPI, PostgreSQL, Kubernetes",
            "why_suitable": "5+ years developing cloud backends and high-concurrency APIs.",
        }
        cv_text = _build_cv_text_from_answers(answers)
        self.assertIn("Fatima Zahra", cv_text)
        self.assertIn("fatima.zahra@example.com", cv_text)
        self.assertIn("BS Software Engineering", cv_text)
        self.assertIn("Senior Backend Developer", cv_text)
        self.assertIn("FastAPI", cv_text)

    @patch("portal.google_form_sync_service.build")
    @patch("portal.google_form_sync_service.resolve_google_workspace_credentials")
    @patch("portal.cv_scoring_service._score_cv_with_groq")
    def test_03_sync_job_form_responses_end_to_end(self, mock_groq, mock_creds, mock_build):
        mock_creds.return_value = MagicMock(token="mock_token")

        mock_forms = MagicMock()
        mock_build.return_value = mock_forms

        mock_forms.forms().get().execute.return_value = {
            "formId": "mock_google_form_12345",
            "items": [
                {"title": "Full Name", "questionItem": {"question": {"questionId": "q1"}}},
                {"title": "Email Address", "questionItem": {"question": {"questionId": "q2"}}},
                {"title": "Total Professional Experience (Years)", "questionItem": {"question": {"questionId": "q3"}}},
                {"title": "Primary Technical Skills", "questionItem": {"question": {"questionId": "q4"}}},
            ],
        }

        mock_forms.forms().responses().list().execute.return_value = {
            "responses": [
                {
                    "responseId": "resp_001_unique",
                    "createTime": "2026-11-15T18:00:00Z",
                    "answers": {
                        "q1": {"textAnswers": {"answers": [{"value": "Bilal Ahmed"}]}},
                        "q2": {"textAnswers": {"answers": [{"value": "bilal.ahmed.sync@example.com"}]}},
                        "q3": {"textAnswers": {"answers": [{"value": "6"}]}},
                        "q4": {"textAnswers": {"answers": [{"value": "Python, Django, Docker, Postgres"}]}},
                    },
                }
            ]
        }

        mock_groq.return_value = {
            "candidate": {
                "full_name": "Bilal Ahmed",
                "email": "bilal.ahmed.sync@example.com",
                "phone": "+92-300-9876543",
                "location": "Lahore, Pakistan",
            },
            "parsed_cv": {
                "extracted_skills": ["Python", "Django", "Docker", "Postgres"],
                "experience_years": 6.0,
                "highest_degree": "Bachelor's",
                "work_history": [{"company": "Alpha Tech", "role": "Backend Lead", "years": 4}],
                "education": [{"degree": "BS CS", "institution": "FAST-NUCES", "year": 2018}],
            },
            "scores": {
                "skill_match_score": 92.0,
                "experience_match_score": 90.0,
                "education_match_score": 88.0,
            },
            "analysis": {
                "matched_skills": ["Python", "Django", "Postgres", "Docker"],
                "missing_skills": [],
                "skill_rationale": "Perfect skill match for requirements.",
                "experience_rationale": "6 years exceed the 4 years requirement.",
                "education_rationale": "Relevant CS degree.",
                "strengths": ["Strong backend experience"],
                "concerns": [],
                "ai_summary": "Top applicant with extensive Python background.",
            },
        }

        Application.objects.filter(source_message_id="resp_001_unique").delete()
        # First run: should sync 1 new application
        res = sync_job_form_responses(self.job)
        self.assertTrue(res["ok"])
        self.assertEqual(res["synced_count"], 1)
        self.assertEqual(res["total_responses"], 1)
        app = Application.objects.filter(job_posting=self.job, source_message_id="resp_001_unique").first()
        self.assertIsNotNone(app)
        self.assertEqual(app.candidate.email, "bilal.ahmed.sync@example.com")
        self.assertEqual(app.source, "web_form")
        self.assertGreaterEqual(float(app.cv_evaluation.overall_score), 85.0)

        # Second run: idempotent, should skip the already synced response
        res2 = sync_job_form_responses(self.job)
        self.assertTrue(res2["ok"])
        self.assertEqual(res2["synced_count"], 0)
        self.assertEqual(res2["skipped_count"], 1)

    def test_04_management_command_execution(self):
        # Call command programmatically to verify arguments and flow
        call_command("sync_google_form_responses", job_id=str(self.job.id))


if __name__ == "__main__":
    unittest.main()
