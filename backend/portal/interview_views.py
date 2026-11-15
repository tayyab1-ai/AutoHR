"""Views for candidate interview invitations, self-scheduling, mandatory consent gate, and interview room."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .decorators import hr_login_required
from .interview_execution_service import (
    complete_stage_and_progress,
    evaluate_question_answer,
    get_or_generate_stage_questions,
)
from .interview_invitation_service import (
    bulk_invite_shortlisted,
    complete_consent_and_initialize_interview,
    create_or_refresh_candidate_invitation,
    generate_available_slots,
    schedule_candidate_interview,
)
from .models import (
    Application,
    CandidateFinalRanking,
    CandidateInvitation,
    Interview,
    InterviewConsent,
    InterviewQuestionAnswer,
    InterviewSchedule,
    InterviewStage,
    JobPosting,
)
from .services import get_job_for_company

_logger = logging.getLogger(__name__)


def _json_body(request) -> dict:
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            pass
    return request.POST.dict()


# ==============================================================================
# HR Authenticated APIs (Dashboard)
# ==============================================================================


@hr_login_required
@require_POST
def invite_candidate_api(request, application_id):
    """HR triggers an interview invitation with a secure magic link for a shortlisted candidate."""
    company = request.user.db_user.company
    try:
        app = Application.objects.select_related("candidate", "job_posting").get(
            id=application_id,
            job_posting__company=company,
        )
    except (Application.DoesNotExist, ValueError):
        return JsonResponse({"ok": False, "error": "Application not found."}, status=404)

    base_url = request.build_absolute_uri("/").rstrip("/")
    invitation, full_url = create_or_refresh_candidate_invitation(app, base_url=base_url)

    return JsonResponse(
        {
            "ok": True,
            "message": f"Interview invitation created for {app.candidate.full_name}.",
            "invitation": {
                "id": str(invitation.id),
                "magic_token": invitation.magic_token,
                "invitation_url": full_url,
                "expires_at": invitation.expires_at.isoformat(),
                "candidate_name": app.candidate.full_name,
                "candidate_email": app.candidate.email,
                "job_title": app.job_posting.title,
                "status": app.status,
            },
        }
    )


@hr_login_required
@require_POST
def bulk_invite_candidates_api(request, job_id):
    """HR triggers invitations for all shortlisted candidates for a job."""
    company = request.user.db_user.company
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    base_url = request.build_absolute_uri("/").rstrip("/")
    result = bulk_invite_shortlisted(job, base_url=base_url)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Sent {result['invited_count']} invitation(s).",
            "invited_count": result["invited_count"],
            "candidates": result["candidates"],
        }
    )


# ==============================================================================
# Candidate Self-Scheduling & Consent Public Views
# ==============================================================================


def candidate_interview_portal_view(request, magic_token: str):
    """Public portal: Candidate accesses their invitation to schedule or proceed to interview."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).select_related(
        "application__candidate",
        "application__job_posting__company",
    ).first()

    if not invitation:
        return render(
            request,
            "interview/interview_expired.html",
            {"error_title": "Invalid Invitation", "error_message": "This invitation link was not found or has been revoked."},
            status=404,
        )

    if invitation.is_expired():
        return render(
            request,
            "interview/interview_expired.html",
            {"error_title": "Invitation Expired", "error_message": "This interview invitation has expired. Please contact the hiring team."},
            status=410,
        )

    app = invitation.application
    candidate = app.candidate
    job = app.job_posting
    company = job.company

    # Check existing schedule and consent
    schedule = InterviewSchedule.objects.filter(application=app).order_by("-created_at").first()
    consent = InterviewConsent.objects.filter(interview_schedule=schedule).first() if schedule else None

    # If already consented and scheduled, offer jump to room or show confirmed status
    slots = generate_available_slots(days_ahead=5)

    context = {
        "invitation": invitation,
        "application": app,
        "candidate": candidate,
        "job": job,
        "company": company,
        "schedule": schedule,
        "consent": consent,
        "available_slots": slots,
        "magic_token": magic_token,
    }
    return render(request, "interview/candidate_interview_portal.html", context)


@require_POST
def candidate_schedule_slot_api(request, magic_token: str):
    """Public API: Candidate selects an interview time slot."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).select_related(
        "application__candidate",
        "application__job_posting",
    ).first()

    if not invitation or invitation.is_expired():
        return JsonResponse({"ok": False, "error": "This invitation is invalid or has expired."}, status=403)

    data = _json_body(request)
    start_iso = data.get("scheduled_start")
    end_iso = data.get("scheduled_end")
    tz_name = data.get("timezone", "Asia/Karachi")

    if not start_iso or not end_iso:
        return JsonResponse({"ok": False, "error": "Please select a valid time slot."}, status=400)

    try:
        start_dt = datetime.fromisoformat(start_iso)
        end_dt = datetime.fromisoformat(end_iso)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)
    except (ValueError, TypeError) as exc:
        return JsonResponse({"ok": False, "error": f"Invalid date/time format: {exc}"}, status=400)

    if end_dt <= start_dt:
        return JsonResponse({"ok": False, "error": "Slot end must be after slot start."}, status=400)

    room_url = f"/interview/{magic_token}/room/"
    schedule = schedule_candidate_interview(
        invitation,
        scheduled_start=start_dt,
        scheduled_end=end_dt,
        timezone_name=tz_name,
        room_url=room_url,
    )

    return JsonResponse(
        {
            "ok": True,
            "message": "Interview slot reserved. Please complete the consent confirmation.",
            "schedule": {
                "id": str(schedule.id),
                "scheduled_start": schedule.scheduled_start.isoformat(),
                "scheduled_end": schedule.scheduled_end.isoformat(),
                "timezone": schedule.timezone,
            },
        }
    )


@require_POST
def candidate_submit_consent_api(request, magic_token: str):
    """Public API: Candidate submits mandatory recording and AI processing consent."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).select_related(
        "application",
    ).first()

    if not invitation or invitation.is_expired():
        return JsonResponse({"ok": False, "error": "This invitation is invalid or has expired."}, status=403)

    schedule = InterviewSchedule.objects.filter(application=invitation.application).order_by("-created_at").first()
    if not schedule:
        return JsonResponse({"ok": False, "error": "Please select a schedule slot first."}, status=400)

    data = _json_body(request)
    consent_rec = bool(data.get("consent_recording"))
    consent_ai = bool(data.get("consent_ai_processing"))

    if not consent_rec or not consent_ai:
        return JsonResponse(
            {
                "ok": False,
                "error": "Both audio/video recording consent and AI evaluation consent are mandatory.",
            },
            status=400,
        )

    ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "127.0.0.1"
    ua = request.META.get("HTTP_USER_AGENT") or ""

    try:
        consent, interview = complete_consent_and_initialize_interview(
            schedule,
            consent_recording=consent_rec,
            consent_ai_processing=consent_ai,
            ip_address=ip,
            user_agent=ua,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "message": "Consent confirmed. Ready to enter interview room.",
            "room_url": f"/interview/{magic_token}/room/",
        }
    )


def candidate_interview_room_view(request, magic_token: str):
    """Public Interview Room: Candidate conducts the 3-stage AI interview."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).select_related(
        "application__candidate",
        "application__job_posting__company",
    ).first()

    if not invitation:
        return render(
            request,
            "interview/interview_expired.html",
            {"error_title": "Invalid Session", "error_message": "Interview session not found."},
            status=404,
        )

    app = invitation.application
    schedule = InterviewSchedule.objects.filter(application=app).order_by("-created_at").first()
    if not schedule:
        return redirect(f"/interview/{magic_token}/")

    consent = InterviewConsent.objects.filter(interview_schedule=schedule).first()
    if not consent:
        return redirect(f"/interview/{magic_token}/")

    interview = Interview.objects.filter(application=app, interview_schedule=schedule).first()
    stages = list(interview.stages.all().order_by("sequence_order")) if interview else []

    context = {
        "invitation": invitation,
        "application": app,
        "candidate": app.candidate,
        "job": app.job_posting,
        "company": app.job_posting.company,
        "schedule": schedule,
        "interview": interview,
        "stages": stages,
        "magic_token": magic_token,
    }
    return render(request, "interview/candidate_interview_room.html", context)


@require_GET
def candidate_stage_questions_api(request, magic_token: str, sequence_order: int):
    """Retrieve or generate dynamic questions for an interview stage."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).first()
    if not invitation or invitation.is_expired():
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)

    interview = (
        Interview.objects.filter(application=invitation.application)
        .order_by("-created_at")
        .first()
    )
    if not interview:
        return JsonResponse({"ok": False, "error": "Interview session not initialized."}, status=404)

    stage = InterviewStage.objects.filter(interview=interview, sequence_order=sequence_order).first()
    if not stage:
        return JsonResponse({"ok": False, "error": f"Stage {sequence_order} not found."}, status=404)

    if stage.status == "not_started":
        stage.status = "in_progress"
        stage.started_at = timezone.now()
        stage.save(update_fields=["status", "started_at"])

    questions = get_or_generate_stage_questions(stage)
    return JsonResponse(
        {
            "ok": True,
            "stage": {
                "sequence_order": stage.sequence_order,
                "stage_type": stage.stage_type,
                "status": stage.status,
            },
            "questions": [
                {
                    "id": str(q.id),
                    "question_number": q.question_number,
                    "question_text": q.question_text,
                    "answered": bool(q.transcript_text),
                    "communication_score": float(q.communication_score) if q.communication_score is not None else None,
                    "technical_score": float(q.technical_score) if q.technical_score is not None else None,
                    "problem_solving_score": float(q.problem_solving_score) if q.problem_solving_score is not None else None,
                    "ai_rationale": q.ai_rationale or "",
                }
                for q in questions
            ],
        }
    )


@require_POST
def candidate_submit_answer_api(request, magic_token: str, question_id):
    """Submit candidate's answer (audio file or transcript) and evaluate with 5-factor AI rubric."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).first()
    if not invitation or invitation.is_expired():
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)

    qa = InterviewQuestionAnswer.objects.select_related("stage__interview__application").filter(
        id=question_id,
        stage__interview__application=invitation.application,
    ).first()
    if not qa:
        return JsonResponse({"ok": False, "error": "Question not found."}, status=404)

    # Extract answer text and duration
    answer_text = request.POST.get("answer_text") or ""
    duration_sec = request.POST.get("duration_seconds") or 0

    if not answer_text and request.body:
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            answer_text = body_data.get("answer_text") or answer_text
            duration_sec = body_data.get("duration_seconds") or duration_sec
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    audio_file = request.FILES.get("audio")
    audio_bytes = audio_file.read() if audio_file else None
    audio_name = audio_file.name if audio_file else "answer.webm"

    evaluated_qa = evaluate_question_answer(
        qa,
        answer_text=answer_text,
        duration_seconds=int(duration_sec or 0),
        audio_bytes=audio_bytes,
        audio_filename=audio_name,
    )

    return JsonResponse(
        {
            "ok": True,
            "message": "Answer evaluated successfully.",
            "question": {
                "id": str(evaluated_qa.id),
                "question_number": evaluated_qa.question_number,
                "transcript": evaluated_qa.transcript_text,
                "scores": {
                    "communication": float(evaluated_qa.communication_score or 0),
                    "confidence": float(evaluated_qa.confidence_score or 0),
                    "technical": float(evaluated_qa.technical_score or 0),
                    "relevance": float(evaluated_qa.relevance_score or 0),
                    "problem_solving": float(evaluated_qa.problem_solving_score or 0),
                },
                "ai_rationale": evaluated_qa.ai_rationale,
            },
        }
    )


@require_POST
def candidate_complete_stage_api(request, magic_token: str, sequence_order: int):
    """Mark stage completed and transition to next stage or finalize interview."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).first()
    if not invitation or invitation.is_expired():
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)

    interview = (
        Interview.objects.filter(application=invitation.application)
        .order_by("-created_at")
        .first()
    )
    if not interview:
        return JsonResponse({"ok": False, "error": "Interview not found."}, status=404)

    stage = InterviewStage.objects.filter(interview=interview, sequence_order=sequence_order).first()
    if not stage:
        return JsonResponse({"ok": False, "error": "Stage not found."}, status=404)

    res = complete_stage_and_progress(stage)
    return JsonResponse({"ok": True, **res})


# ==============================================================================
# HR Leaderboard APIs
# ==============================================================================


@hr_login_required
@require_GET
def job_leaderboard_api(request, job_id):
    """Retrieve full candidate leaderboard with CV, Interview, and Composite rankings."""
    company = request.user.db_user.company
    try:
        job = get_job_for_company(job_id, company)
    except JobPosting.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    rankings = CandidateFinalRanking.objects.filter(job_posting=job).select_related(
        "application__candidate"
    ).order_by("final_rank")

    data = [
        {
            "id": str(r.id),
            "final_rank": r.final_rank,
            "candidate_name": r.application.candidate.full_name,
            "candidate_email": r.application.candidate.email,
            "cv_score": float(r.cv_score),
            "interview_score": float(r.interview_score),
            "composite_score": float(r.composite_score),
            "decision_verdict": r.decision_verdict,
            "ai_justification": r.ai_justification,
            "hr_override_verdict": r.hr_override_verdict,
            "hr_feedback_notes": r.hr_feedback_notes,
            "calculated_at": r.calculated_at.isoformat(),
        }
        for r in rankings
    ]

    return JsonResponse({"ok": True, "job_title": job.title, "leaderboard": data})


@hr_login_required
@require_POST
def hr_override_ranking_api(request, ranking_id):
    """HR overrides AI verdict or adds human review feedback notes."""
    company = request.user.db_user.company
    ranking = CandidateFinalRanking.objects.select_related("job_posting").filter(
        id=ranking_id,
        job_posting__company=company,
    ).first()
    if not ranking:
        return JsonResponse({"ok": False, "error": "Ranking record not found."}, status=404)

    body = _json_body(request)
    verdict = (body.get("override_verdict") or "").strip().lower()
    notes = (body.get("feedback_notes") or "").strip()

    valid_verdicts = {"strong_hire", "hire", "lean_hire", "no_hire", ""}
    if verdict not in valid_verdicts:
        return JsonResponse({"ok": False, "error": "Invalid verdict option."}, status=400)

    ranking.hr_override_verdict = verdict or None
    ranking.hr_feedback_notes = notes or None
    ranking.save(update_fields=["hr_override_verdict", "hr_feedback_notes"])

    return JsonResponse(
        {
            "ok": True,
            "message": "Ranking override saved successfully.",
            "ranking": {
                "id": str(ranking.id),
                "hr_override_verdict": ranking.hr_override_verdict,
                "hr_feedback_notes": ranking.hr_feedback_notes,
            },
        }
    )


