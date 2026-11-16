"""AI Live Interview Execution Engine: Question Generation, Audio STT (Whisper),
5-Factor Rubric Scoring, Interview Rollup, and Final Leaderboard Ranking.
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from groq import Groq

from .groq_jd import call_groq_chat, groq_model_name
from .models import (
    Application,
    CandidateFinalRanking,
    Interview,
    InterviewEvaluation,
    InterviewQuestionAnswer,
    InterviewStage,
    JobPosting,
    ParsedCv,
)

_logger = logging.getLogger(__name__)

WHISPER_MODEL = "whisper-large-v3"
CV_WEIGHT_RATIO = Decimal("0.40")
INTERVIEW_WEIGHT_RATIO = Decimal("0.60")


def _quantize_rubric(value: float | Decimal | int | str) -> Decimal:
    """Clamps and rounds rubric score between 0.00 and 10.00."""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        dec = Decimal("5.00")
    clamped = max(Decimal("0.00"), min(Decimal("10.00"), dec))
    return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_100(value: float | Decimal | int | str) -> Decimal:
    """Clamps and rounds composite score between 0.00 and 100.00."""
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        dec = Decimal("50.00")
    clamped = max(Decimal("0.00"), min(Decimal("100.00"), dec))
    return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def transcribe_candidate_audio(audio_bytes: bytes, filename: str = "answer.webm") -> str:
    """Transcribe candidate recorded audio using Groq Whisper API (whisper-large-v3)."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or "your-groq" in api_key.lower():
        _logger.warning("GROQ_API_KEY placeholder detected. Audio transcription falling back.")
        return ""

    try:
        client = Groq(api_key=api_key)
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model=WHISPER_MODEL,
            response_format="json",
        )
        return (getattr(transcription, "text", "") or "").strip()
    except Exception as exc:
        _logger.warning("Groq Whisper transcription failed: %s", exc)
        return ""


def _save_interview_audio(stage_id: str, question_num: int, audio_bytes: bytes, filename: str) -> str:
    """Save candidate audio response to MEDIA_ROOT and return public URL."""
    rel_dir = Path("interviews") / str(stage_id)
    target_dir = Path(settings.MEDIA_ROOT) / rel_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix or ".webm"
    stored_name = f"q{question_num}_{timezone.now().strftime('%Y%m%d%H%M%S')}{ext}"
    (target_dir / stored_name).write_bytes(audio_bytes)
    media_prefix = "/" + settings.MEDIA_URL.strip("/")
    return f"{media_prefix}/interviews/{stage_id}/{stored_name}"


# ==============================================================================
# Question Generation (Stage-aware & CV-personalized)
# ==============================================================================


DEFAULT_QUESTIONS = {
    "screening": [
        "Please introduce yourself and explain what motivated you to apply for this role.",
        "Can you describe your most significant professional achievement and what made it impactful?",
    ],
    "technical": [
        "How do you design and structure applications using the core technologies required for this position?",
        "Walk us through a complex technical issue or production bug you resolved. What was your diagnosis and fix?",
    ],
    "behavioral": [
        "Describe a situation where you had a disagreement with a team member or stakeholder. How did you resolve it?",
    ],
}


def get_or_generate_stage_questions(stage: InterviewStage) -> list[InterviewQuestionAnswer]:
    """Retrieve existing questions for an interview stage or generate them using Groq AI."""
    existing = list(stage.questions_answers.all().order_by("question_number"))
    if existing:
        return existing

    interview = stage.interview
    app = interview.application
    job = app.job_posting
    candidate = app.candidate
    parsed_cv = getattr(app, "parsed_cv", None)

    stage_type = stage.stage_type.lower()
    target_count = 2 if stage_type in {"screening", "technical"} else 1

    prompt_context = {
        "job_title": job.title,
        "department": job.department,
        "required_skills": job.required_skills or [],
        "min_experience_years": job.min_experience_years,
        "candidate_name": candidate.full_name,
        "candidate_skills": parsed_cv.extracted_skills if parsed_cv else [],
        "candidate_exp_years": float(parsed_cv.extracted_experience_years) if parsed_cv and parsed_cv.extracted_experience_years else None,
        "stage_type": stage_type,
        "question_count": target_count,
    }

    system_prompt = (
        "You are an expert AI Technical Recruiter for AutoHR. "
        "Generate focused, professional interview questions tailored to the candidate's background and job requirements. "
        "Respond ONLY with a JSON object in this exact schema: {\"questions\": [\"question 1 text\", \"question 2 text\"]}"
    )

    user_prompt = (
        f"Generate {target_count} high-quality interview questions for the '{stage_type}' stage.\n"
        f"Job Details: Title='{job.title}', Department='{job.department}', Required Skills={job.required_skills}.\n"
        f"Candidate Details: Name='{candidate.full_name}', Skills={prompt_context['candidate_skills']}, Experience Years={prompt_context['candidate_exp_years']}.\n"
        f"Stage Focus:\n"
        f"- screening: 2 questions on self-introduction, motivations, career trajectory, and high-level fit.\n"
        f"- technical: 2 deep technical questions targeting required skills ({job.required_skills}), system architecture, problem-solving, and practical debugging.\n"
        f"- behavioral: 1 question on ownership, conflict resolution, collaboration, or handling tight deadlines."
    )

    question_texts = []
    try:
        raw_res = call_groq_chat(system_prompt, user_prompt, json_mode=True, temperature=0.3, max_tokens=900)
        data = json.loads(raw_res)
        if isinstance(data.get("questions"), list) and data["questions"]:
            question_texts = [str(q).strip() for q in data["questions"] if str(q).strip()]
    except Exception as exc:
        _logger.warning("Groq question generation fallback: %s", exc)

    if not question_texts:
        # Fallback to high-quality defaults tailored with job title
        base_qs = DEFAULT_QUESTIONS.get(stage_type, DEFAULT_QUESTIONS["screening"])
        question_texts = [q.replace("this role", f"the {job.title} position") for q in base_qs[:target_count]]

    created_questions = []
    with transaction.atomic():
        for i, q_text in enumerate(question_texts, start=1):
            qa = InterviewQuestionAnswer.objects.create(
                stage=stage,
                question_number=i,
                question_text=q_text,
            )
            created_questions.append(qa)

    return created_questions


# ==============================================================================
# Question Answer 5-Factor Rubric Scoring
# ==============================================================================


def evaluate_question_answer(
    qa: InterviewQuestionAnswer,
    answer_text: str,
    *,
    duration_seconds: int = 0,
    audio_bytes: bytes | None = None,
    audio_filename: str = "answer.webm",
) -> InterviewQuestionAnswer:
    """Evaluate a candidate's answer across the 5 rubric criteria using Groq AI.

    5 Criteria (0.0 to 10.0):
      1. Communication Score: Articulation, clarity, structure.
      2. Confidence Score: Composure, assurance, flow.
      3. Technical Score: Depth of technical knowledge, domain accuracy.
      4. Relevance Score: Directness of addressing the specific question asked.
      5. Problem Solving Score: Logical reasoning, analytical approach, tradeoffs.
    """
    stage = qa.stage
    job = stage.interview.application.job_posting

    clean_answer = (answer_text or "").strip()

    # Save audio if provided
    audio_url = None
    if audio_bytes:
        audio_url = _save_interview_audio(str(stage.id), qa.question_number, audio_bytes, audio_filename)
        # If text was not supplied, transcribe audio
        if not clean_answer:
            clean_answer = transcribe_candidate_audio(audio_bytes, audio_filename)

    if not clean_answer:
        # Nothing to evaluate: record a zero score instead of asking the AI (or guessing).
        qa.transcript_text = "[No audible response or transcript provided.]"
        qa.duration_seconds = max(0, int(duration_seconds or 0))
        if audio_url:
            qa.audio_clip_url = audio_url
        qa.communication_score = qa.confidence_score = qa.technical_score = Decimal("0.00")
        qa.relevance_score = qa.problem_solving_score = Decimal("0.00")
        qa.ai_rationale = "No answer was given for this question."
        qa.save()
        return qa

    system_prompt = (
        "You are an objective AI Interview Evaluator. Evaluate the candidate's response to the interview question. "
        "Score the answer on five specific competency dimensions from 0.0 to 10.0:\n"
        "- communication_score (0-10): Clarity, verbal structure, conciseness.\n"
        "- confidence_score (0-10): Assertiveness, poise, conviction.\n"
        "- technical_score (0-10): Technical correctness, depth, terminology.\n"
        "- relevance_score (0-10): Did the response directly answer what was asked?\n"
        "- problem_solving_score (0-10): Analytical reasoning, practical tradeoff considerations.\n"
        "Provide a concise ai_rationale explaining the scores.\n"
        "Respond ONLY with a JSON object matching this schema:\n"
        "{\n"
        "  \"communication_score\": 8.5,\n"
        "  \"confidence_score\": 8.0,\n"
        "  \"technical_score\": 7.5,\n"
        "  \"relevance_score\": 9.0,\n"
        "  \"problem_solving_score\": 8.0,\n"
        "  \"ai_rationale\": \"Strong clarity and relevant technical context.\"\n"
        "}"
    )

    user_prompt = (
        f"Role: {job.title}\n"
        f"Stage: {stage.stage_type}\n"
        f"Question #{qa.question_number}: \"{qa.question_text}\"\n"
        f"Candidate Answer: \"{clean_answer}\"\n"
        f"Answer Duration: {duration_seconds} seconds.\n"
    )

    # Neutral fallback used only if the AI evaluation is unavailable; flagged for HR review.
    scores = {
        "communication_score": Decimal("5.00"),
        "confidence_score": Decimal("5.00"),
        "technical_score": Decimal("5.00"),
        "relevance_score": Decimal("5.00"),
        "problem_solving_score": Decimal("5.00"),
        "ai_rationale": "AI evaluation was unavailable; neutral score assigned. Please review this answer manually.",
    }

    try:
        raw_res = call_groq_chat(system_prompt, user_prompt, json_mode=True, temperature=0.2, max_tokens=700)
        payload = json.loads(raw_res)
        scores["communication_score"] = _quantize_rubric(payload.get("communication_score"))
        scores["confidence_score"] = _quantize_rubric(payload.get("confidence_score"))
        scores["technical_score"] = _quantize_rubric(payload.get("technical_score"))
        scores["relevance_score"] = _quantize_rubric(payload.get("relevance_score"))
        scores["problem_solving_score"] = _quantize_rubric(payload.get("problem_solving_score"))
        scores["ai_rationale"] = str(payload.get("ai_rationale") or "").strip() or scores["ai_rationale"]
    except Exception as exc:
        _logger.warning("Groq answer evaluation fallback: %s", exc)
        # Deterministic heuristic fallback if empty / placeholder
        if len(clean_answer) < 30:
            scores["communication_score"] = Decimal("3.00")
            scores["confidence_score"] = Decimal("3.00")
            scores["technical_score"] = Decimal("3.00")
            scores["relevance_score"] = Decimal("3.00")
            scores["problem_solving_score"] = Decimal("3.00")
            scores["ai_rationale"] = (
                "AI evaluation was unavailable and the response was very brief. Please review this answer manually."
            )

    qa.transcript_text = clean_answer
    qa.duration_seconds = max(0, int(duration_seconds or 0))
    if audio_url:
        qa.audio_clip_url = audio_url
    qa.communication_score = scores["communication_score"]
    qa.confidence_score = scores["confidence_score"]
    qa.technical_score = scores["technical_score"]
    qa.relevance_score = scores["relevance_score"]
    qa.problem_solving_score = scores["problem_solving_score"]
    qa.ai_rationale = scores["ai_rationale"]
    qa.save()

    return qa


# ==============================================================================
# Stage Advancement & Interview Rollup Evaluation
# ==============================================================================


@transaction.atomic
def complete_stage_and_progress(stage: InterviewStage) -> dict[str, Any]:
    """Mark current stage as completed and activate next stage, or complete interview."""
    now = timezone.now()
    stage.status = "completed"
    stage.ended_at = now
    stage.save(update_fields=["status", "ended_at"])

    interview = stage.interview

    # Check for next stage
    next_stage = (
        InterviewStage.objects.filter(interview=interview, sequence_order__gt=stage.sequence_order)
        .order_by("sequence_order")
        .first()
    )

    if next_stage:
        next_stage.status = "in_progress"
        next_stage.started_at = now
        next_stage.save(update_fields=["status", "started_at"])
        # Ensure questions are ready for next stage
        get_or_generate_stage_questions(next_stage)
        return {
            "interview_completed": False,
            "next_stage": {
                "sequence_order": next_stage.sequence_order,
                "stage_type": next_stage.stage_type,
            },
        }

    # All stages completed! Finalize interview
    interview.status = "completed"
    interview.ended_at = now
    interview.save(update_fields=["status", "ended_at"])

    # Compute rollup evaluation and update leaderboard
    evaluation = evaluate_full_interview(interview)
    ranking = update_candidate_final_ranking(interview.application)

    return {
        "interview_completed": True,
        "evaluation_id": str(evaluation.id),
        "composite_interview_score": float(evaluation.composite_interview_score),
        "final_rank": ranking.final_rank,
        "decision_verdict": ranking.decision_verdict,
    }


def evaluate_full_interview(interview: Interview) -> InterviewEvaluation:
    """Roll up all 5-factor question answers into the overall interview evaluation."""
    now = timezone.now()
    # Every generated question counts; an unanswered question scores 0 (skipping is never rewarded).
    answers = list(InterviewQuestionAnswer.objects.filter(stage__interview=interview))

    def _avg(field: str) -> Decimal:
        if not answers:
            return Decimal("0.00")
        total = sum(Decimal(str(getattr(a, field) or 0)) for a in answers)
        return _quantize_rubric(total / Decimal(len(answers)))

    comm_avg = _avg("communication_score")
    conf_avg = _avg("confidence_score")
    tech_avg = _avg("technical_score")
    rel_avg = _avg("relevance_score")
    prob_avg = _avg("problem_solving_score")

    # Composite interview score out of 100: sum of 5 dimension averages * 2
    raw_composite = (comm_avg + conf_avg + tech_avg + rel_avg + prob_avg) * Decimal("2.0")
    composite_score = _quantize_100(raw_composite)

    app = interview.application
    job = app.job_posting
    candidate = app.candidate

    # Rollup AI summary, strengths & weaknesses via Groq
    system_prompt = (
        "You are an executive hiring board advisor. Summarize the interview results for the candidate. "
        "Provide strengths (list of strings), weaknesses (list of strings), and an executive_summary (text). "
        "Respond ONLY with a JSON object matching this schema:\n"
        "{\n"
        "  \"strengths\": [\"string 1\", \"string 2\"],\n"
        "  \"weaknesses\": [\"string 1\", \"string 2\"],\n"
        "  \"executive_summary\": \"Comprehensive summary text.\"\n"
        "}"
    )

    user_prompt = (
        f"Candidate: {candidate.full_name}\n"
        f"Role: {job.title} ({job.department})\n"
        f"Scores: Communication={comm_avg}/10, Confidence={conf_avg}/10, Technical={tech_avg}/10, Relevance={rel_avg}/10, ProblemSolving={prob_avg}/10.\n"
        f"Overall Interview Score: {composite_score}/100.\n"
        f"Transcripts:\n" + "\n".join([f"Q{a.question_number}: {a.question_text}\nA: {a.transcript_text}" for a in answers[:5]])
    )

    strengths = ["Strong core communication", "Demonstrated relevant domain exposure"]
    weaknesses = ["Could provide more concrete production metric examples"]
    exec_summary = f"{candidate.full_name} completed the 3-stage interview with an overall score of {composite_score}%."

    try:
        raw_res = call_groq_chat(system_prompt, user_prompt, json_mode=True, temperature=0.3, max_tokens=900)
        data = json.loads(raw_res)
        if isinstance(data.get("strengths"), list) and data["strengths"]:
            strengths = [str(s).strip() for s in data["strengths"] if str(s).strip()][:5]
        if isinstance(data.get("weaknesses"), list) and data["weaknesses"]:
            weaknesses = [str(w).strip() for w in data["weaknesses"] if str(w).strip()][:5]
        if data.get("executive_summary"):
            exec_summary = str(data["executive_summary"]).strip()
    except Exception as exc:
        _logger.warning("Groq rollup evaluation fallback: %s", exc)

    evaluation, _ = InterviewEvaluation.objects.update_or_create(
        interview=interview,
        defaults={
            "communication_avg": comm_avg,
            "confidence_avg": conf_avg,
            "technical_avg": tech_avg,
            "relevance_avg": rel_avg,
            "problem_solving_avg": prob_avg,
            "composite_interview_score": composite_score,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "executive_summary": exec_summary,
            "evaluated_at": now,
        },
    )

    return evaluation


# ==============================================================================
# Final Ranking & Leaderboard Calculation (Step 10)
# ==============================================================================


@transaction.atomic
def update_candidate_final_ranking(application: Application) -> CandidateFinalRanking:
    """Calculate composite score (CV + Interview), determine verdict, and recalculate job leaderboard."""
    job = application.job_posting
    now = timezone.now()

    # Retrieve CV score
    cv_score = Decimal("0.00")
    if hasattr(application, "cv_evaluation") and application.cv_evaluation:
        cv_score = _quantize_100(application.cv_evaluation.overall_score)

    # Retrieve Interview score
    interview = getattr(application, "interviews", None)
    interview_obj = application.interviews.filter(status="completed").order_by("-created_at").first()
    interview_score = Decimal("0.00")
    if interview_obj and hasattr(interview_obj, "evaluation") and interview_obj.evaluation:
        interview_score = _quantize_100(interview_obj.evaluation.composite_interview_score)

    # Composite formula: (CV Score * 0.40) + (Interview Score * 0.60)
    composite_score = _quantize_100((cv_score * CV_WEIGHT_RATIO) + (interview_score * INTERVIEW_WEIGHT_RATIO))

    # Decision verdict mapping (strong_hire, hire, lean_hire, no_hire)
    if composite_score >= Decimal("85.00"):
        verdict = "strong_hire"
    elif composite_score >= Decimal("70.00"):
        verdict = "hire"
    elif composite_score >= Decimal("55.00"):
        verdict = "lean_hire"
    else:
        verdict = "no_hire"

    justification = (
        f"Combined evaluation of CV ({cv_score}%) and 3-stage AI interview ({interview_score}%) "
        f"yielded an aggregate competency score of {composite_score}%, qualifying as {verdict.replace('_', ' ').upper()}."
    )

    # Update or create candidate's own ranking row with temporary unique rank
    ranking, created = CandidateFinalRanking.objects.get_or_create(
        application=application,
        defaults={
            "job_posting": job,
            "final_rank": 9999,  # Placeholder, recomputed immediately below
            "cv_score": cv_score,
            "interview_score": interview_score,
            "composite_score": composite_score,
            "decision_verdict": verdict,
            "ai_justification": justification,
            "recording_retained": False,
            "calculated_at": now,
        },
    )

    if not created:
        ranking.job_posting = job
        ranking.cv_score = cv_score
        ranking.interview_score = interview_score
        ranking.composite_score = composite_score
        ranking.decision_verdict = verdict
        ranking.ai_justification = justification
        ranking.calculated_at = now
        ranking.save(
            update_fields=[
                "job_posting",
                "cv_score",
                "interview_score",
                "composite_score",
                "decision_verdict",
                "ai_justification",
                "calculated_at",
            ]
        )

    application.status = "final_review"
    application.updated_at = now
    application.save(update_fields=["status", "updated_at"])

    # Re-calculate clean sequential ranks for the job (1, 2, 3...)
    # Negative buffering prevents uq_job_rank collision during update
    all_rankings = list(
        CandidateFinalRanking.objects.filter(job_posting=job).order_by("-composite_score", "calculated_at")
    )

    # 1. Temporarily buffer with positive high-offset values to avoid uq_job_rank collision
    for idx, r in enumerate(all_rankings, start=1):
        CandidateFinalRanking.objects.filter(id=r.id).update(final_rank=1000000 + idx)

    # 2. Assign final 1-based ranks
    for idx, r in enumerate(all_rankings, start=1):
        CandidateFinalRanking.objects.filter(id=r.id).update(final_rank=idx)
        if r.id == ranking.id:
            ranking.final_rank = idx

    ranking.refresh_from_db()
    return ranking
