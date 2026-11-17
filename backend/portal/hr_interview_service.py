"""HR-only interview data: live/scheduled/completed list and full per-question evaluations.

Candidates never receive any of this; it is served only to signed-in HR of the owning company.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from .models import (
    CandidateFinalRanking,
    CandidateInvitation,
    Interview,
    InterviewConsent,
    InterviewEvaluation,
    InterviewQuestionAnswer,
    InterviewSchedule,
)

STATUS_LABELS = {
    "live": "Live now",
    "scheduled": "Scheduled",
    "awaiting_consent": "Awaiting consent",
    "completed": "Completed",
    "missed": "Missed",
}


def _f(value) -> float | None:
    return float(value) if value is not None else None


def _row_for_schedule(schedule: InterviewSchedule, now) -> dict[str, Any]:
    app = schedule.application
    interview = (
        Interview.objects.filter(application=app, interview_schedule=schedule).order_by("-created_at").first()
        or Interview.objects.filter(application=app).order_by("-created_at").first()
    )
    local_start = timezone.localtime(schedule.scheduled_start)

    stage_label = "Not started"
    answered = total = 0
    score = None
    if interview:
        qas = InterviewQuestionAnswer.objects.filter(stage__interview=interview)
        total = qas.count()
        answered = qas.exclude(transcript_text__isnull=True).exclude(transcript_text="").count()
        current = (
            interview.stages.filter(status__in=["in_progress", "completed"]).order_by("-sequence_order").first()
        )
        if current:
            stage_label = f"Stage {current.sequence_order}: {current.stage_type.title()}"
        ev = InterviewEvaluation.objects.filter(interview=interview).first()
        if ev:
            score = _f(ev.composite_interview_score)

    if interview and interview.status == "completed":
        status = "completed"
        stage_label = "All 3 stages"
    elif interview and interview.status == "in_progress":
        status = "live"
    elif interview:
        # Consent given but not started yet.
        status = "missed" if now > schedule.scheduled_end + timedelta(hours=2) else "scheduled"
    elif InterviewConsent.objects.filter(interview_schedule=schedule).exists():
        status = "scheduled"
    else:
        status = "awaiting_consent"

    return {
        "schedule_id": str(schedule.id),
        "interview_id": str(interview.id) if interview else None,
        "application_id": str(app.id),
        "candidate": app.candidate.full_name,
        "email": app.candidate.email,
        "role": app.job_posting.title,
        "stage": stage_label,
        "date": local_start.strftime("%d %b %Y"),
        "time": local_start.strftime("%I:%M %p"),
        "start_iso": local_start.isoformat(),
        "status": status,
        "status_label": STATUS_LABELS[status],
        "answered": answered,
        "total_questions": total,
        "score": score,
        "has_details": bool(interview),  # HR can open it (and reset the link) as soon as it exists
    }


def interview_rows_for_company(company, *, limit: int = 50) -> list[dict[str, Any]]:
    """Interviews for the HR dashboard, live ones first, then upcoming, then most recent."""
    now = timezone.now()
    schedules = (
        InterviewSchedule.objects.filter(application__job_posting__company=company)
        .select_related("application__candidate", "application__job_posting")
        .order_by("-scheduled_start")[:limit]
    )
    rows = [_row_for_schedule(s, now) for s in schedules]
    order = {"live": 0, "scheduled": 1, "awaiting_consent": 2, "completed": 3, "missed": 4}
    rows.sort(key=lambda r: (order[r["status"]], r["start_iso"] if r["status"] in ("scheduled", "awaiting_consent") else ""))
    # Within completed/missed show newest first.
    head = [r for r in rows if r["status"] in ("live", "scheduled", "awaiting_consent")]
    tail = sorted(
        (r for r in rows if r["status"] in ("completed", "missed")), key=lambda r: r["start_iso"], reverse=True
    )
    return head + tail


def interview_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    today = timezone.localdate().strftime("%d %b %Y")
    return {
        "live": sum(1 for r in rows if r["status"] == "live"),
        "upcoming": sum(1 for r in rows if r["status"] in ("scheduled", "awaiting_consent")),
        "today": sum(1 for r in rows if r["date"] == today and r["status"] != "missed"),
        "completed": sum(1 for r in rows if r["status"] == "completed"),
    }


def interview_detail_for_company(interview_id, company) -> dict[str, Any] | None:
    """Full evaluation of one interview for HR: every question, transcript, 5 scores, rationale."""
    interview = (
        Interview.objects.select_related("application__candidate", "application__job_posting", "interview_schedule")
        .filter(id=interview_id, application__job_posting__company=company)
        .first()
    )
    if not interview:
        return None
    app = interview.application
    stages = []
    for stage in interview.stages.all().order_by("sequence_order"):
        questions = []
        for qa in InterviewQuestionAnswer.objects.filter(stage=stage).order_by("question_number"):
            answered = bool(qa.transcript_text)
            scores = {
                "communication": _f(qa.communication_score),
                "confidence": _f(qa.confidence_score),
                "technical": _f(qa.technical_score),
                "relevance": _f(qa.relevance_score),
                "problem_solving": _f(qa.problem_solving_score),
            }
            vals = [v for v in scores.values() if v is not None]
            questions.append(
                {
                    "number": qa.question_number,
                    "question": qa.question_text,
                    "answered": answered,
                    "transcript": qa.transcript_text or "",
                    "duration_seconds": qa.duration_seconds,
                    "audio_url": qa.audio_clip_url or "",
                    "scores": scores,
                    "average": round(sum(vals) / len(vals), 2) if vals and answered else None,
                    "ai_rationale": qa.ai_rationale or "",
                }
            )
        stages.append(
            {
                "order": stage.sequence_order,
                "type": stage.stage_type,
                "status": stage.status,
                "questions": questions,
            }
        )

    evaluation = InterviewEvaluation.objects.filter(interview=interview).first()
    ranking = CandidateFinalRanking.objects.filter(application=app).first()
    invitation = CandidateInvitation.objects.filter(application=app).first()
    schedule = interview.interview_schedule
    return {
        "id": str(interview.id),
        "status": interview.status,
        "candidate": app.candidate.full_name,
        "email": app.candidate.email,
        "role": app.job_posting.title,
        "scheduled": timezone.localtime(schedule.scheduled_start).strftime("%d %b %Y, %I:%M %p") if schedule else "",
        "started_at": timezone.localtime(interview.started_at).strftime("%d %b %Y, %I:%M %p") if interview.started_at else "",
        "ended_at": timezone.localtime(interview.ended_at).strftime("%d %b %Y, %I:%M %p") if interview.ended_at else "",
        "stages": stages,
        "link_locked": bool(invitation and invitation.room_lock_hash),
        "link_opened_at": (
            timezone.localtime(invitation.room_opened_at).strftime("%d %b %Y, %I:%M %p")
            if invitation and invitation.room_opened_at
            else ""
        ),
        "evaluation": (
            {
                "composite": _f(evaluation.composite_interview_score),
                "averages": {
                    "communication": _f(evaluation.communication_avg),
                    "confidence": _f(evaluation.confidence_avg),
                    "technical": _f(evaluation.technical_avg),
                    "relevance": _f(evaluation.relevance_avg),
                    "problem_solving": _f(evaluation.problem_solving_avg),
                },
                "strengths": list(evaluation.strengths or []),
                "weaknesses": list(evaluation.weaknesses or []),
                "summary": evaluation.executive_summary or "",
            }
            if evaluation
            else None
        ),
        "ranking": (
            {
                "final_rank": ranking.final_rank,
                "cv_score": _f(ranking.cv_score),
                "interview_score": _f(ranking.interview_score),
                "composite": _f(ranking.composite_score),
                "verdict": ranking.decision_verdict,
                "hr_override": ranking.hr_override_verdict,
            }
            if ranking
            else None
        ),
    }
