"""Automated verification suite for Sprint 1: Candidate Invitations, Self-Scheduling & Mandatory Consent Gate."""

import os
import sys
import unittest
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import django

django.setup()

from django.test import Client, TestCase
from django.utils import timezone

from portal.interview_invitation_service import (
    bulk_invite_shortlisted,
    complete_consent_and_initialize_interview,
    create_or_refresh_candidate_invitation,
    generate_available_slots,
    schedule_candidate_interview,
)
from portal.models import (
    Application,
    Candidate,
    CandidateInvitation,
    Company,
    EmailNotification,
    Interview,
    InterviewConsent,
    InterviewSchedule,
    InterviewStage,
    JobPosting,
    User,
)


class TestInterviewSprint1(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        now = timezone.now()
        cls.company, _ = Company.objects.get_or_create(
            name="Sprint 1 Tech Corp",
            defaults={"city": "Karachi", "country": "Pakistan"},
        )
        cls.user, _ = User.objects.get_or_create(
            email="hr_sprint1@techcorp.internal",
            defaults={
                "company": cls.company,
                "full_name": "Sprint 1 Lead HR",
                "password_hash": "dummy_hash",
                "role": "hr_manager",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.job, _ = JobPosting.objects.get_or_create(
            company=cls.company,
            title="Senior Full-Stack AI Engineer",
            defaults={
                "created_by": cls.user,
                "department": "Engineering",
                "job_category": "Software",
                "employment_type": "Full-time",
                "work_mode": "Hybrid",
                "city": "Karachi",
                "target_hires": 2,
                "job_description": "We are looking for an exceptional full-stack AI engineer.",
                "posting_date": now.date(),
                "application_deadline": (now + timedelta(days=20)).date(),
                "min_experience_years": 4,
                "min_education_level": "Bachelor's",
                "required_skills": ["Python", "Django", "React", "TypeScript", "PostgreSQL"],
                "job_post_tone": "Professional",
                "cv_skill_weight": 50,
                "cv_experience_weight": 30,
                "cv_education_weight": 20,
                "cv_min_passing_score": 60,
                "status": "approved",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.candidate, _ = Candidate.objects.get_or_create(
            email="candidate.sprint1@example.com",
            defaults={
                "full_name": "Kamran Khan",
                "phone": "+92-321-4567890",
                "location": "Karachi, Pakistan",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.app, _ = Application.objects.get_or_create(
            job_posting=cls.job,
            candidate=cls.candidate,
            defaults={
                "source": "web_form",
                "resume_file_url": "/media/resumes/dummy.pdf",
                "resume_original_filename": "kamran_cv.pdf",
                "resume_mime_type": "application/pdf",
                "status": "shortlisted",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.app.status = "shortlisted"
        cls.app.save(update_fields=["status"])

    def test_01_invitation_generation(self):
        invitation, url = create_or_refresh_candidate_invitation(self.app, base_url="http://localhost:8000")
        self.assertIsNotNone(invitation)
        self.assertTrue(len(invitation.magic_token) >= 32)
        self.assertIn(invitation.magic_token, url)
        self.assertFalse(invitation.is_used)
        self.assertFalse(invitation.is_expired())

        # Verify application status
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "interview_invited")

        # Verify email notification logged
        email_record = (
            EmailNotification.objects.filter(
                application=self.app,
                recipient_email=self.candidate.email,
                notification_type="interview_invite",
            )
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(email_record)
        self.assertIn("Interview Invitation", email_record.subject)
        self.assertIn(invitation.magic_token, email_record.body_text)

    def test_02_available_slots_generator(self):
        slots = generate_available_slots(days_ahead=3)
        self.assertTrue(len(slots) > 0)
        first_slot = slots[0]
        self.assertIn("start_iso", first_slot)
        self.assertIn("end_iso", first_slot)
        self.assertIn("day_label", first_slot)
        self.assertIn("time_label", first_slot)

    def test_03_candidate_portal_public_access(self):
        invitation = CandidateInvitation.objects.filter(application=self.app).first()
        # Valid invitation
        resp = self.client.get(f"/interview/{invitation.magic_token}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Senior Full-Stack AI Engineer")
        self.assertContains(resp, "Kamran Khan")
        self.assertContains(resp, "Mandatory Gate")

        # Invalid token
        resp_invalid = self.client.get("/interview/non_existent_token_12345/")
        self.assertEqual(resp_invalid.status_code, 404)

    def test_04_self_scheduling_and_mandatory_consent_flow(self):
        invitation = CandidateInvitation.objects.filter(application=self.app).first()
        now = timezone.now() + timedelta(days=2)
        slot_start = now.replace(hour=14, minute=0, second=0, microsecond=0)
        slot_end = slot_start + timedelta(minutes=45)

        # 1. Schedule slot via API
        resp = self.client.post(
            f"/interview/{invitation.magic_token}/schedule/",
            data={
                "scheduled_start": slot_start.isoformat(),
                "scheduled_end": slot_end.isoformat(),
                "timezone": "Asia/Karachi",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "interview_scheduled")

        schedule = InterviewSchedule.objects.filter(application=self.app).first()
        self.assertIsNotNone(schedule)

        # 2. Consent refusal / incomplete consent should fail
        resp_refusal = self.client.post(
            f"/interview/{invitation.magic_token}/consent/",
            data={
                "consent_recording": False,
                "consent_ai_processing": True,
            },
            content_type="application/json",
        )
        self.assertEqual(resp_refusal.status_code, 400)
        self.assertFalse(resp_refusal.json()["ok"])

        # 3. Full explicit consent accepted
        resp_consent = self.client.post(
            f"/interview/{invitation.magic_token}/consent/",
            data={
                "consent_recording": True,
                "consent_ai_processing": True,
            },
            content_type="application/json",
            HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0",
        )
        self.assertEqual(resp_consent.status_code, 200)
        consent_data = resp_consent.json()
        self.assertTrue(consent_data["ok"])
        self.assertIn("/room/", consent_data["room_url"])

        # Verify DB records
        consent = InterviewConsent.objects.filter(interview_schedule=schedule).first()
        self.assertIsNotNone(consent)
        self.assertTrue(consent.consent_recording)
        self.assertTrue(consent.consent_ai_processing)

        # Verify pre-provisioned interview & 3 stages
        interview = Interview.objects.filter(application=self.app).first()
        self.assertIsNotNone(interview)
        self.assertEqual(interview.status, "pending")

        stages = list(interview.stages.all().order_by("sequence_order"))
        self.assertEqual(len(stages), 3)
        self.assertEqual(stages[0].stage_type, "screening")
        self.assertEqual(stages[1].stage_type, "technical")
        self.assertEqual(stages[2].stage_type, "behavioral")

        # Verify invitation marked accepted/used
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_used)
        self.assertIsNotNone(invitation.accepted_at)

        # 4. Access Interview Room
        resp_room = self.client.get(f"/interview/{invitation.magic_token}/room/")
        self.assertEqual(resp_room.status_code, 200)
        self.assertContains(resp_room, "AutoHR AI Interviewer")
        self.assertContains(resp_room, "Stage 1: Screening")
        self.assertContains(resp_room, "Audio Feed")


if __name__ == "__main__":
    unittest.main()
