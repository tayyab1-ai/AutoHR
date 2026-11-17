"""Views for candidate interview invitations, self-scheduling, mandatory consent gate, and interview room."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .decorators import hr_login_required
from .interview_execution_service import (
    transcribe_candidate_audio,
    complete_stage_and_progress,
    evaluate_question_answer,
    get_or_generate_stage_questions,
)
from .interview_invitation_service import (
    InvitationNotAllowed,
    START_NOW,
    SchedulingNotAllowed,
    bulk_invite_shortlisted,
    complete_consent_and_initialize_interview,
    generate_available_slots,
    invite_and_email,
    safe_client_ip,
    schedule_candidate_interview,
    validate_requested_slot,
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
from .hr_interview_service import (
    interview_detail_for_company,
    interview_rows_for_company,
    interview_summary,
)
from .services import get_job_for_company

_logger = logging.getLogger(__name__)

MAX_AUDIO_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB per answer
ROOM_EARLY_ACCESS = timedelta(minutes=getattr(settings, "INTERVIEW_ROOM_EARLY_ACCESS_MINUTES", 15))


def _active_invitation(magic_token: str):
    """Invitation for this token if it exists and has not expired, else None."""
    invitation = CandidateInvitation.objects.filter(magic_token=magic_token).select_related(
        "application__candidate",
        "application__job_posting__company",
    ).first()
    if not invitation or invitation.is_expired():
        return None
    return invitation


# ---------------------------------------------------------------------------
# Single-use interview links
# The first browser that opens the interview room is bound to the link with a secret,
# httpOnly cookie (only its SHA-256 hash is stored). That browser may reload/reconnect;
# any other browser or device is refused. HR can reset the binding from the dashboard.
# ---------------------------------------------------------------------------

LINK_USED_TITLE = "Interview Link Already Used"
LINK_USED_MESSAGE = (
    "This interview link has already been opened on another browser or device. "
    "For security, each interview link can only be used once. If this was you and your "
    "browser closed unexpectedly, please reply to the hiring team's email so they can reset your link."
)


def _lock_cookie_name(invitation) -> str:
    return f"ahr_room_{invitation.id.hex[:16]}"


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _room_lock_state(request, invitation) -> str:
    """'free' (never opened), 'owner' (this browser holds the link) or 'other'."""
    if not invitation.room_lock_hash:
        return "free"
    secret = request.COOKIES.get(_lock_cookie_name(invitation), "")
    if secret and secrets.compare_digest(_hash_secret(secret), invitation.room_lock_hash):
        return "owner"
    return "other"


def _claim_room_lock(invitation) -> str | None:
    """Atomically bind the link to a new browser secret; None if another browser won the race."""
    secret = secrets.token_urlsafe(32)
    claimed = CandidateInvitation.objects.filter(id=invitation.id, room_lock_hash__isnull=True).update(
        room_lock_hash=_hash_secret(secret),
        room_opened_at=timezone.now(),
    )
    if not claimed:
        return None
    invitation.room_lock_hash = _hash_secret(secret)
    return secret


def _set_lock_cookie(response, invitation, magic_token: str, secret: str) -> None:
    max_age = max(3600, int((invitation.expires_at - timezone.now()).total_seconds()))
    response.set_cookie(
        _lock_cookie_name(invitation),
        secret,
        max_age=max_age,
        path=f"/interview/{magic_token}/",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="Lax",
    )


def _link_used_page(request):
    return render(
        request,
        "interview/interview_expired.html",
        {"error_title": LINK_USED_TITLE, "error_message": LINK_USED_MESSAGE},
        status=403,
    )


def _require_room_owner(request, invitation):
    """JSON error unless this browser is the one that opened the interview room."""
    state = _room_lock_state(request, invitation)
    if state == "owner":
        return None
    if state == "other":
        return JsonResponse({"ok": False, "link_used": True, "error": LINK_USED_MESSAGE}, status=403)
    return JsonResponse({"ok": False, "error": "Please open the interview room from your invitation link first."}, status=403)


def _latest_interview(application):
    return Interview.objects.filter(application=application).order_by("-created_at").first()


def _room_open_error(application) -> str | None:
    """Reason the candidate cannot act in the interview room right now, or None."""
    schedule = InterviewSchedule.objects.filter(application=application).order_by("-created_at").first()
    if not schedule or not InterviewConsent.objects.filter(interview_schedule=schedule).exists():
        return "Please schedule your interview and accept the consent conditions first."
    if timezone.now() < schedule.scheduled_start - ROOM_EARLY_ACCESS:
        local_start = timezone.localtime(schedule.scheduled_start)
        return f"Your interview room opens at {local_start.strftime('%B %d, %Y %I:%M %p')}."
    return None


def _previous_stages_completed(stage: InterviewStage) -> bool:
    return not InterviewStage.objects.filter(
        interview=stage.interview,
        sequence_order__lt=stage.sequence_order,
    ).exclude(status__in=["completed", "skipped"]).exists()


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
    try:
        result = invite_and_email(app, base_url=base_url, sender_user_id=request.user.db_user.id)
    except InvitationNotAllowed as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=409)
    invitation = result["invitation"]
    full_url = result["invitation_url"]
    app.refresh_from_db(fields=["status"])

    if result["email_sent"]:
        message = f"Interview invitation emailed to {app.candidate.email}."
    else:
        message = f"Invitation link created for {app.candidate.full_name}, but the email was not sent."

    return JsonResponse(
        {
            "ok": True,
            "message": message,
            "invitation": {
                "id": str(invitation.id),
                "magic_token": invitation.magic_token,
                "invitation_url": full_url,
                "expires_at": invitation.expires_at.isoformat(),
                "candidate_name": app.candidate.full_name,
                "candidate_email": app.candidate.email,
                "job_title": app.job_posting.title,
                "status": app.status,
                "email_sent": result["email_sent"],
                "email_error": result["email_error"],
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
    result = bulk_invite_shortlisted(job, base_url=base_url, sender_user_id=request.user.db_user.id)
    invited = result["invited_count"]
    emailed = result["emailed_count"]
    if invited == 0:
        message = "No shortlisted candidates are waiting for an invitation."
    elif emailed == invited:
        message = f"Emailed {emailed} interview invitation(s)."
    else:
        message = (
            f"Created {invited} invitation link(s); {emailed} emailed, "
            f"{invited - emailed} not emailed (send those links manually)."
        )
    return JsonResponse(
        {
            "ok": True,
            "message": message,
            "invited_count": invited,
            "emailed_count": emailed,
            "candidates": result["candidates"],
        }
    )


# ==============================================================================
# Candidate Self-Scheduling & Consent Public Views
# ==============================================================================


@ensure_csrf_cookie
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

    interview = _latest_interview(app)
    if interview and interview.status == "completed":
        return render(
            request,
            "interview/interview_expired.html",
            {
                "error_title": "Interview Completed",
                "error_message": "You have already completed this interview. The hiring team will be in touch.",
            },
            status=410,
        )
    if consent:
        # Already scheduled and consented: go straight to the room.
        return redirect(f"/interview/{magic_token}/room/")

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
        "allow_start_now": getattr(settings, "INTERVIEW_ALLOW_START_NOW", False),
        "magic_token": magic_token,
    }
    return render(request, "interview/candidate_interview_portal.html", context)


@require_POST
def candidate_schedule_slot_api(request, magic_token: str):
    """Public API: Candidate selects an interview time slot."""
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "This invitation is invalid or has expired."}, status=403)

    data = _json_body(request)
    start_iso = data.get("scheduled_start")
    if not start_iso or not isinstance(start_iso, str):
        return JsonResponse({"ok": False, "error": "Please select a valid time slot."}, status=400)

    try:
        if start_iso == START_NOW:
            start_dt = START_NOW
        else:
            start_dt = datetime.fromisoformat(start_iso)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
        # Only slots the portal offered are accepted; the end time is derived server-side.
        start_dt, end_dt = validate_requested_slot(start_dt)
        room_url = f"/interview/{magic_token}/room/"
        schedule = schedule_candidate_interview(
            invitation,
            scheduled_start=start_dt,
            scheduled_end=end_dt,
            timezone_name=settings.TIME_ZONE,
            room_url=room_url,
        )
    except (ValueError, TypeError) as exc:
        # SchedulingNotAllowed is a ValueError with a user-facing message.
        message = str(exc) if isinstance(exc, SchedulingNotAllowed) else "Invalid date/time for the selected slot."
        return JsonResponse({"ok": False, "error": message}, status=400)

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
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "This invitation is invalid or has expired."}, status=403)
    if _room_lock_state(request, invitation) == "other":
        return JsonResponse({"ok": False, "link_used": True, "error": LINK_USED_MESSAGE}, status=403)

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

    ip = safe_client_ip(request)
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


@ensure_csrf_cookie
def candidate_interview_room_view(request, magic_token: str):
    """Public Interview Room: Candidate conducts the 3-stage AI interview."""
    invitation = _active_invitation(magic_token)

    if not invitation:
        return render(
            request,
            "interview/interview_expired.html",
            {"error_title": "Invalid Session", "error_message": "This interview link was not found or has expired."},
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
    if interview and interview.status == "completed":
        return render(
            request,
            "interview/interview_expired.html",
            {
                "error_title": "Interview Completed",
                "error_message": "You have already completed this interview. The hiring team will be in touch.",
            },
            status=410,
        )

    not_open = _room_open_error(app)
    if not_open:
        # Scheduled for later: show a candidate-only confirmation (no links into AutoHR).
        opens_at = schedule.scheduled_start - ROOM_EARLY_ACCESS
        return render(
            request,
            "interview/interview_scheduled.html",
            {
                "candidate": app.candidate,
                "job": app.job_posting,
                "company": app.job_posting.company,
                "local_start": timezone.localtime(schedule.scheduled_start),
                "local_end": timezone.localtime(schedule.scheduled_end),
                "timezone_label": "PKT" if settings.TIME_ZONE == "Asia/Karachi" else settings.TIME_ZONE,
                "early_minutes": int(ROOM_EARLY_ACCESS.total_seconds() // 60),
                "seconds_until_open": max(0, int((opens_at - timezone.now()).total_seconds())),
            },
        )

    # Single-use link: bind to this browser on first entry; refuse every other browser.
    new_secret = None
    lock_state = _room_lock_state(request, invitation)
    if lock_state == "free":
        new_secret = _claim_room_lock(invitation)
        if not new_secret:
            invitation.refresh_from_db(fields=["room_lock_hash", "room_opened_at"])
            lock_state = _room_lock_state(request, invitation)
    if lock_state == "other":
        return _link_used_page(request)

    stages = list(interview.stages.all().order_by("sequence_order")) if interview else []
    resume_stage_order = next((st.sequence_order for st in stages if st.status not in ("completed", "skipped")), 1)

    context = {
        "invitation": invitation,
        "application": app,
        "candidate": app.candidate,
        "job": app.job_posting,
        "company": app.job_posting.company,
        "schedule": schedule,
        "interview": interview,
        "stages": stages,
        "resume_stage_order": resume_stage_order,
        "magic_token": magic_token,
    }
    response = render(request, "interview/candidate_interview_room.html", context)
    if new_secret:
        _set_lock_cookie(response, invitation, magic_token, new_secret)
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def candidate_stage_questions_api(request, magic_token: str, sequence_order: int):
    """Retrieve or generate dynamic questions for an interview stage."""
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)
    denied = _require_room_owner(request, invitation)
    if denied:
        return denied

    interview = _latest_interview(invitation.application)
    if not interview:
        return JsonResponse({"ok": False, "error": "Interview session not initialized."}, status=404)
    if interview.status == "completed":
        return JsonResponse({"ok": False, "error": "This interview has already been completed."}, status=409)
    not_open = _room_open_error(invitation.application)
    if not_open:
        return JsonResponse({"ok": False, "error": not_open}, status=403)

    stage = InterviewStage.objects.filter(interview=interview, sequence_order=sequence_order).first()
    if not stage:
        return JsonResponse({"ok": False, "error": f"Stage {sequence_order} not found."}, status=404)
    if not _previous_stages_completed(stage):
        return JsonResponse({"ok": False, "error": "Please complete the earlier stages first."}, status=409)

    if stage.status == "not_started":
        stage.status = "in_progress"
        stage.started_at = timezone.now()
        stage.save(update_fields=["status", "started_at"])

    if interview.status == "pending":
        # First question opened: the interview is now live (shown as "Live now" to HR).
        now = timezone.now()
        interview.status = "in_progress"
        interview.started_at = interview.started_at or now
        interview.save(update_fields=["status", "started_at"])
        app = invitation.application
        if app.status in ("interview_invited", "interview_scheduled"):
            app.status = "interview_in_progress"
            app.updated_at = now
            app.save(update_fields=["status", "updated_at"])

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
                    # Evaluation results are for HR only and are never sent to the candidate.
                }
                for q in questions
            ],
        }
    )


@require_POST
def candidate_submit_answer_api(request, magic_token: str, question_id):
    """Submit candidate's answer (audio file or transcript) and evaluate with 5-factor AI rubric."""
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)
    denied = _require_room_owner(request, invitation)
    if denied:
        return denied

    qa = InterviewQuestionAnswer.objects.select_related("stage__interview__application").filter(
        id=question_id,
        stage__interview__application=invitation.application,
    ).first()
    if not qa:
        return JsonResponse({"ok": False, "error": "Question not found."}, status=404)

    not_open = _room_open_error(invitation.application)
    if not_open:
        return JsonResponse({"ok": False, "error": not_open}, status=403)
    if qa.stage.interview.status == "completed" or qa.stage.status != "in_progress":
        return JsonResponse({"ok": False, "error": "This interview stage is not open for answers."}, status=409)
    if qa.transcript_text:
        # One attempt per question: answers cannot be resubmitted for a better score.
        return JsonResponse(
            {"ok": False, "already_answered": True, "error": "This question has already been answered."},
            status=409,
        )

    # Extract answer text and duration
    answer_text = request.POST.get("answer_text") or ""
    duration_sec = request.POST.get("duration_seconds") or 0

    # Only JSON requests carry a raw body to parse. Multipart uploads (audio) have already
    # been read into request.POST/FILES, and touching request.body again raises an error.
    if not answer_text and (request.content_type or "").startswith("application/json"):
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            answer_text = body_data.get("answer_text") or answer_text
            duration_sec = body_data.get("duration_seconds") or duration_sec
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    try:
        duration_int = max(0, min(int(float(duration_sec or 0)), 3600))
    except (TypeError, ValueError):
        duration_int = 0
    answer_text = str(answer_text or "")[:20000]

    audio_file = request.FILES.get("audio")
    if audio_file and audio_file.size > MAX_AUDIO_UPLOAD_BYTES:
        return JsonResponse({"ok": False, "error": "Audio recording is too large (max 20 MB)."}, status=413)
    audio_bytes = audio_file.read() if audio_file else None
    audio_name = audio_file.name if audio_file else "answer.webm"

    evaluated_qa = evaluate_question_answer(
        qa,
        answer_text=answer_text,
        duration_seconds=duration_int,
        audio_bytes=audio_bytes,
        audio_filename=audio_name,
    )

    # The answer is evaluated and stored for HR; the candidate only gets a confirmation.
    return JsonResponse(
        {
            "ok": True,
            "message": "Answer saved.",
            "question": {
                "id": str(evaluated_qa.id),
                "question_number": evaluated_qa.question_number,
            },
        }
    )


LIVE_TRANSCRIBE_MIN_INTERVAL_SECONDS = 2


@require_POST
def candidate_live_transcribe_api(request, magic_token: str, question_id):
    """Live speech-to-text while the candidate is answering.

    The room uploads the audio recorded so far every few seconds; we return the Whisper
    transcript so it can be shown live. Nothing is saved or scored here.
    """
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)
    denied = _require_room_owner(request, invitation)
    if denied:
        return denied

    qa = InterviewQuestionAnswer.objects.select_related("stage__interview").filter(
        id=question_id,
        stage__interview__application=invitation.application,
    ).first()
    if not qa:
        return JsonResponse({"ok": False, "error": "Question not found."}, status=404)
    not_open = _room_open_error(invitation.application)
    if not_open:
        return JsonResponse({"ok": False, "error": not_open}, status=403)
    if qa.transcript_text or qa.stage.status != "in_progress" or qa.stage.interview.status == "completed":
        return JsonResponse({"ok": False, "error": "This question is not open for answers."}, status=409)

    audio_file = request.FILES.get("audio")
    if not audio_file or audio_file.size == 0:
        return JsonResponse({"ok": True, "text": ""})
    if audio_file.size > MAX_AUDIO_UPLOAD_BYTES:
        return JsonResponse({"ok": False, "error": "Recording is too long (max 20 MB)."}, status=413)

    # Simple per-question throttle so a page can't flood the speech-to-text API.
    throttle_key = f"live-transcribe:{qa.id}"
    if not cache.add(throttle_key, 1, timeout=LIVE_TRANSCRIBE_MIN_INTERVAL_SECONDS):
        return JsonResponse({"ok": False, "throttled": True, "error": "Too many requests."}, status=429)

    audio_bytes = audio_file.read()
    text = transcribe_candidate_audio(audio_bytes, audio_file.name or "answer.webm", live=True)
    return JsonResponse({"ok": True, "text": text, "audio_bytes": len(audio_bytes)})


@require_POST
def candidate_complete_stage_api(request, magic_token: str, sequence_order: int):
    """Mark stage completed and transition to next stage or finalize interview."""
    invitation = _active_invitation(magic_token)
    if not invitation:
        return JsonResponse({"ok": False, "error": "Invalid or expired session."}, status=403)
    denied = _require_room_owner(request, invitation)
    if denied:
        return denied

    interview = _latest_interview(invitation.application)
    if not interview:
        return JsonResponse({"ok": False, "error": "Interview not found."}, status=404)
    if interview.status == "completed":
        return JsonResponse({"ok": False, "error": "This interview has already been completed."}, status=409)

    stage = InterviewStage.objects.filter(interview=interview, sequence_order=sequence_order).first()
    if not stage:
        return JsonResponse({"ok": False, "error": "Stage not found."}, status=404)
    if stage.status != "in_progress" or not _previous_stages_completed(stage):
        return JsonResponse({"ok": False, "error": "This stage cannot be completed right now."}, status=409)

    stage_questions = InterviewQuestionAnswer.objects.filter(stage=stage)
    if not stage_questions.exists():
        return JsonResponse({"ok": False, "error": "This stage has no questions yet."}, status=409)
    unanswered = stage_questions.filter(Q(transcript_text__isnull=True) | Q(transcript_text="")).count()
    if unanswered:
        return JsonResponse(
            {"ok": False, "error": f"Please answer all questions first ({unanswered} remaining)."},
            status=409,
        )

    res = complete_stage_and_progress(stage)
    # Scores, rank and verdict stay on the HR dashboard only.
    candidate_view = {
        "interview_completed": bool(res.get("interview_completed")),
        "next_stage": res.get("next_stage"),
    }
    return JsonResponse({"ok": True, **candidate_view})


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


# ==============================================================================
# HR interview monitoring (dashboard only — never exposed to candidates)
# ==============================================================================


@hr_login_required
@require_GET
def hr_interviews_list_api(request):
    """Live / upcoming / completed interviews for the signed-in HR user's company."""
    company = request.user.db_user.company
    rows = interview_rows_for_company(company)
    return JsonResponse({"ok": True, "interviews": rows, "summary": interview_summary(rows)})


@hr_login_required
@require_GET
def hr_interview_detail_api(request, interview_id):
    """Per-question transcript, 5-factor scores and AI rationale for one interview."""
    detail = interview_detail_for_company(interview_id, request.user.db_user.company)
    if not detail:
        return JsonResponse({"ok": False, "error": "Interview not found."}, status=404)
    return JsonResponse({"ok": True, "interview": detail})


@hr_login_required
@require_POST
def hr_reset_interview_link_api(request, interview_id):
    """Let the candidate re-open their link on a new browser (e.g. their computer crashed)."""
    company = request.user.db_user.company
    interview = Interview.objects.select_related("application").filter(
        id=interview_id,
        application__job_posting__company=company,
    ).first()
    if not interview:
        return JsonResponse({"ok": False, "error": "Interview not found."}, status=404)
    if interview.status == "completed":
        return JsonResponse({"ok": False, "error": "This interview is already completed."}, status=409)
    updated = CandidateInvitation.objects.filter(application=interview.application).update(
        room_lock_hash=None,
        room_opened_at=None,
    )
    if not updated:
        return JsonResponse({"ok": False, "error": "No invitation link found for this candidate."}, status=404)
    return JsonResponse(
        {
            "ok": True,
            "message": "Link reset. The candidate can now open their interview link once more, on any browser.",
        }
    )
