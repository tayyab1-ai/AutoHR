"""Automated verification suite for Sprint 2: AI Live Interview Execution,
Whisper STT, 5-Factor Rubric Scoring, Interview Rollup & Leaderboard Ranking.
"""

import os
import sys
import unittest
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import django

django.setup()

from django.test import Client, TestCase
from django.utils import timezone

from portal.interview_execution_service import (
    complete_stage_and_progress,
    evaluate_full_interview,
    evaluate_question_answer,
    get_or_generate_stage_questions,
    update_candidate_final_ranking,
)
from portal.interview_invitation_service import (
    complete_consent_and_initialize_interview,
    create_or_refresh_candidate_invitation,
    schedule_candidate_interview,
)
from portal.models import (
    Application,
    Candidate,
    CandidateFinalRanking,
    CandidateInvitation,
    Company,
    CvEvaluation,
    Interview,
    InterviewConsent,
    InterviewEvaluation,
    InterviewQuestionAnswer,
    InterviewSchedule,
    InterviewStage,
    JobPosting,
    User,
)


class TestInterviewSprint2(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        now = timezone.now()
        cls.company, _ = Company.objects.get_or_create(
            name="Sprint 2 AI Lab",
            defaults={"city": "Islamabad", "country": "Pakistan"},
        )
        cls.user, _ = User.objects.get_or_create(
            email="hr_sprint2@ailab.internal",
            defaults={
                "company": cls.company,
                "full_name": "Sprint 2 HR Lead",
                "password_hash": "dummy_hash",
                "role": "hr_manager",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.job, _ = JobPosting.objects.get_or_create(
            company=cls.company,
            title="Senior Python Backend Architect",
            defaults={
                "created_by": cls.user,
                "department": "Engineering",
                "job_category": "Software",
                "employment_type": "Full-time",
                "work_mode": "Remote",
                "city": "Islamabad",
                "target_hires": 1,
                "job_description": "Architect scalable backend services in Python, Django, and Kubernetes.",
                "posting_date": now.date(),
                "application_deadline": (now + timedelta(days=30)).date(),
                "min_experience_years": 5,
                "min_education_level": "Bachelor's",
                "required_skills": ["Python", "Django", "PostgreSQL", "Docker", "Kubernetes"],
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
            email="zainab.sprint2@example.com",
            defaults={
                "full_name": "Zainab Malik",
                "phone": "+92-300-8877665",
                "location": "Islamabad, Pakistan",
                "created_at": now,
                "updated_at": now,
            },
        )
        cls.app, _ = Application.objects.get_or_create(
            job_posting=cls.job,
            candidate=cls.candidate,
            defaults={
                "source": "web_form",
                "resume_file_url": "/media/resumes/zainab.pdf",
                "resume_original_filename": "zainab_cv.pdf",
                "resume_mime_type": "application/pdf",
                "status": "shortlisted",
                "created_at": now,
                "updated_at": now,
            },
        )
        # Seed CV evaluation
        cls.cv_eval, _ = CvEvaluation.objects.get_or_create(
            application=cls.app,
            defaults={
                "overall_score": Decimal("88.00"),
                "skill_match_score": Decimal("90.00"),
                "experience_match_score": Decimal("85.00"),
                "education_match_score": Decimal("88.00"),
                "match_breakdown": {},
                "ai_summary": "Top applicant with extensive cloud background.",
                "is_shortlisted": True,
                "evaluated_at": now,
            },
        )

        # Onboard invitation, schedule, consent, and interview
        cls.invitation, _ = create_or_refresh_candidate_invitation(cls.app)
        start_dt = now + timedelta(days=1)
        end_dt = start_dt + timedelta(minutes=45)
        cls.schedule = schedule_candidate_interview(
            cls.invitation,
            scheduled_start=start_dt,
            scheduled_end=end_dt,
            timezone_name="Asia/Karachi",
        )
        cls.consent, cls.interview = complete_consent_and_initialize_interview(
            cls.schedule,
            consent_recording=True,
            consent_ai_processing=True,
            ip_address="127.0.0.1",
            user_agent="TestRunner",
        )

    def test_01_dynamic_stage_question_generation(self):
        stage1 = self.interview.stages.filter(sequence_order=1).first()
        self.assertIsNotNone(stage1)
        self.assertEqual(stage1.stage_type, "screening")

        questions = get_or_generate_stage_questions(stage1)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0].question_number, 1)
        self.assertEqual(questions[1].question_number, 2)
        self.assertTrue(len(questions[0].question_text) > 10)

        # Calling again should retrieve the existing cached questions without creating duplicates
        questions_repeat = get_or_generate_stage_questions(stage1)
        self.assertEqual(len(questions_repeat), 2)
        self.assertEqual(questions[0].id, questions_repeat[0].id)

    @patch("portal.interview_execution_service.call_groq_chat")
    def test_02_rubric_scoring_and_transcription(self, mock_groq):
        mock_groq.return_value = (
            '{"communication_score": 8.5, "confidence_score": 8.0, '
            '"technical_score": 9.0, "relevance_score": 9.5, "problem_solving_score": 8.5, '
            '"ai_rationale": "Clear technical articulation and solid architectural reasoning."}'
        )

        stage1 = self.interview.stages.filter(sequence_order=1).first()
        questions = get_or_generate_stage_questions(stage1)
        q1 = questions[0]

        evaluated = evaluate_question_answer(
            q1,
            answer_text="I have 6 years experience building distributed backends in Python and Django.",
            duration_seconds=42,
        )

        self.assertEqual(evaluated.communication_score, Decimal("8.50"))
        self.assertEqual(evaluated.technical_score, Decimal("9.00"))
        self.assertEqual(evaluated.relevance_score, Decimal("9.50"))
        self.assertEqual(evaluated.duration_seconds, 42)
        self.assertIn("Clear technical articulation", evaluated.ai_rationale)

    @patch("portal.interview_execution_service.call_groq_chat")
    def test_03_stage_progression_and_interview_rollup(self, mock_groq):
        mock_groq.return_value = (
            '{"strengths": ["Deep Python expertise", "Excellent system design clarity"], '
            '"weaknesses": ["Could discuss Kubernetes telemetry more"], '
            '"executive_summary": "Outstanding candidate for backend architect."}'
        )

        stage1 = self.interview.stages.filter(sequence_order=1).first()
        stage2 = self.interview.stages.filter(sequence_order=2).first()
        stage3 = self.interview.stages.filter(sequence_order=3).first()

        # Score remaining questions for stage 1
        for qa in stage1.questions_answers.all():
            qa.communication_score = Decimal("8.50")
            qa.confidence_score = Decimal("8.00")
            qa.technical_score = Decimal("9.00")
            qa.relevance_score = Decimal("9.00")
            qa.problem_solving_score = Decimal("8.50")
            qa.transcript_text = "Detailed candidate response."
            qa.save()

        # Complete stage 1 -> advances to stage 2
        res1 = complete_stage_and_progress(stage1)
        self.assertFalse(res1["interview_completed"])
        self.assertEqual(res1["next_stage"]["sequence_order"], 2)

        stage2.refresh_from_db()
        self.assertEqual(stage2.status, "in_progress")

        # Score stage 2 questions
        q_s2 = get_or_generate_stage_questions(stage2)
        for qa in q_s2:
            qa.communication_score = Decimal("9.00")
            qa.confidence_score = Decimal("8.50")
            qa.technical_score = Decimal("9.50")
            qa.relevance_score = Decimal("9.00")
            qa.problem_solving_score = Decimal("9.00")
            qa.transcript_text = "Technical depth response."
            qa.save()

        # Complete stage 2 -> advances to stage 3
        res2 = complete_stage_and_progress(stage2)
        self.assertFalse(res2["interview_completed"])
        self.assertEqual(res2["next_stage"]["sequence_order"], 3)

        # Score stage 3 questions
        q_s3 = get_or_generate_stage_questions(stage3)
        for qa in q_s3:
            qa.communication_score = Decimal("8.50")
            qa.confidence_score = Decimal("8.50")
            qa.technical_score = Decimal("8.00")
            qa.relevance_score = Decimal("9.00")
            qa.problem_solving_score = Decimal("8.50")
            qa.transcript_text = "Behavioral conflict resolution response."
            qa.save()

        # Complete stage 3 -> completes entire interview!
        res3 = complete_stage_and_progress(stage3)
        self.assertTrue(res3["interview_completed"])
        self.assertEqual(res3["final_rank"], 1)
        self.assertIn(res3["decision_verdict"], ["strong_hire", "hire"])

        # Check interview evaluation
        self.interview.refresh_from_db()
        self.assertEqual(self.interview.status, "completed")
        evaluation = self.interview.evaluation
        self.assertIsNotNone(evaluation)
        self.assertGreaterEqual(float(evaluation.composite_interview_score), 80.0)
        self.assertTrue(len(evaluation.strengths) > 0)

        # Check candidate final ranking
        ranking = CandidateFinalRanking.objects.filter(application=self.app).first()
        self.assertIsNotNone(ranking)
        self.assertEqual(ranking.final_rank, 1)
        self.assertEqual(ranking.cv_score, Decimal("88.00"))
        self.assertGreaterEqual(float(ranking.composite_score), 80.0)

    def test_04_candidate_interview_apis(self):
        token = self.invitation.magic_token

        # 1. Get questions API for stage 1
        resp_q = self.client.get(f"/interview/{token}/stage/1/questions/")
        self.assertEqual(resp_q.status_code, 200)
        q_data = resp_q.json()
        self.assertTrue(q_data["ok"])
        self.assertTrue(len(q_data["questions"]) >= 1)
        qid = q_data["questions"][0]["id"]

        # 2. Submit answer API
        resp_ans = self.client.post(
            f"/interview/{token}/question/{qid}/answer/",
            data={
                "answer_text": "I designed and deployed a microservice architecture processing 10k RPS.",
                "duration_seconds": 35,
            },
        )
        self.assertEqual(resp_ans.status_code, 200)
        ans_data = resp_ans.json()
        self.assertTrue(ans_data["ok"])
        self.assertIn("scores", ans_data["question"])
        self.assertIn("communication", ans_data["question"]["scores"])


if __name__ == "__main__":
    unittest.main()
