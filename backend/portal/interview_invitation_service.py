"""Interview invitation, magic link generation, email notifications, and candidate scheduling service."""

from __future__ import annotations

import ipaddress
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .email_service import deliver_notification
from .models import (
    Application,
    CandidateInvitation,
    EmailNotification,
    Interview,
    InterviewConsent,
    InterviewSchedule,
    InterviewStage,
    JobPosting,
)

_logger = logging.getLogger(__name__)

DEFAULT_INVITATION_EXPIRY_DAYS = 7
SLOT_DURATION_MINUTES = 45

# Statuses from which HR may (re)send an interview invitation.
INVITABLE_STATUSES = {"shortlisted", "interview_invited", "interview_scheduled"}


class InvitationNotAllowed(ValueError):
    """Raised when HR tries to invite a candidate who is not in an invitable state."""


class SchedulingNotAllowed(ValueError):
    """Raised when a candidate picks an invalid slot or tries to reschedule too late."""


def interview_has_started(application: Application) -> bool:
    """True once the candidate has given consent (the interview session exists)."""
    return Interview.objects.filter(application=application).exists()


def generate_magic_token() -> str:
    """Generate a high-entropy URL-safe magic token."""
    return secrets.token_urlsafe(48)


@transaction.atomic
def create_or_refresh_candidate_invitation(
    application: Application,
    *,
    expiry_days: int = DEFAULT_INVITATION_EXPIRY_DAYS,
    base_url: str = "",
) -> tuple[CandidateInvitation, str]:
    """Create or refresh an interview invitation magic link for a shortlisted candidate.

    - Only shortlisted / already-invited / scheduled (not yet started) candidates are eligible.
    - An active link is kept (same token, expiry extended) so a re-send never breaks it.
    - Once the candidate has consented and started, re-inviting is refused.
    """
    if application.status not in INVITABLE_STATUSES:
        raise InvitationNotAllowed(
            f"Only shortlisted candidates can be invited (current status: {application.status.replace('_', ' ')})."
        )
    if interview_has_started(application):
        raise InvitationNotAllowed("This candidate has already started the interview; their existing link stays active.")

    now = timezone.now()
    expires_at = now + timedelta(days=expiry_days)
    token = generate_magic_token()

    invitation, created = CandidateInvitation.objects.get_or_create(
        application=application,
        defaults={
            "magic_token": token,
            "expires_at": expires_at,
            "is_used": False,
            "sent_at": now,
        },
    )

    if not created:
        if invitation.is_expired():
            invitation.magic_token = token  # expired links are replaced
        invitation.expires_at = expires_at
        invitation.is_used = False
        invitation.sent_at = now
        invitation.accepted_at = None
        invitation.save(update_fields=["magic_token", "expires_at", "is_used", "sent_at", "accepted_at"])

    # Update application status (a scheduled candidate keeps their slot)
    if application.status == "shortlisted":
        application.status = "interview_invited"
        application.updated_at = now
        application.save(update_fields=["status", "updated_at"])

    # Build public interview portal URL
    path = f"/interview/{invitation.magic_token}/"
    full_url = f"{base_url.rstrip('/')}{path}" if base_url else path

    # Record email notification
    candidate = application.candidate
    job = application.job_posting
    company = job.company

    subject = f"Interview Invitation: {job.title} at {company.name}"
    body = (
        f"Dear {candidate.full_name},\n\n"
        f"Congratulations! Based on our review of your application and qualifications, "
        f"{company.name} is delighted to invite you to an AI-assisted interview for the position of {job.title}.\n\n"
        f"Please click the link below to select your interview slot and complete your onboarding:\n"
        f"{full_url}\n\n"
        f"Note: This personal invitation link will expire on {expires_at.strftime('%B %d, %Y at %I:%M %p UTC')}.\n\n"
        f"Best regards,\n"
        f"The Hiring Team at {company.name}"
    )

    invitation._pending_notification = EmailNotification.objects.create(
        application=application,
        recipient_email=candidate.email,
        notification_type="interview_invite",
        subject=subject,
        body_text=body,
        status="queued",
    )

    return invitation, full_url


def invite_and_email(application: Application, *, base_url: str = "", sender_user_id=None) -> dict[str, Any]:
    """Create/refresh the invitation, then email it through the company's connected Gmail.

    Raises InvitationNotAllowed if the candidate is not eligible.
    """
    invitation, full_url = create_or_refresh_candidate_invitation(application, base_url=base_url)
    notification = getattr(invitation, "_pending_notification", None)
    delivery = {"sent": False, "error": "No email was queued."}
    if notification is not None:
        delivery = deliver_notification(
            notification,
            company=application.job_posting.company,
            sender_user_id=sender_user_id,
        )
    return {
        "invitation": invitation,
        "invitation_url": full_url,
        "email_sent": delivery["sent"],
        "email_error": delivery["error"],
    }


def bulk_invite_shortlisted(job: JobPosting, *, base_url: str = "", sender_user_id=None) -> dict[str, Any]:
    """Invite all shortlisted candidates for a job who have not yet received an active invitation."""
    shortlisted_apps = Application.objects.filter(
        job_posting=job,
        status="shortlisted",
    ).select_related("candidate")

    results = []
    for app in shortlisted_apps:
        # Check if already invited and not expired
        existing_inv = getattr(app, "invitation", None)
        if existing_inv and not existing_inv.is_expired() and not existing_inv.is_used:
            continue
        try:
            res = invite_and_email(app, base_url=base_url, sender_user_id=sender_user_id)
        except InvitationNotAllowed:
            continue
        results.append(
            {
                "application_id": str(app.id),
                "candidate_name": app.candidate.full_name,
                "candidate_email": app.candidate.email,
                "invitation_url": res["invitation_url"],
                "email_sent": res["email_sent"],
                "email_error": res["email_error"],
            }
        )

    return {
        "ok": True,
        "invited_count": len(results),
        "emailed_count": sum(1 for r in results if r["email_sent"]),
        "candidates": results,
    }


def generate_available_slots(days_ahead: int = 5) -> list[dict[str, Any]]:
    """Generate available interview time slots for self-scheduling."""
    now = timezone.localtime()  # slot hours are office hours in the configured TIME_ZONE
    slots = []
    # Start looking from tomorrow or today if early
    start_day = 1 if now.hour >= 16 else 0
    slot_hours = [10, 11, 14, 15, 16]  # 10am, 11am, 2pm, 3pm, 4pm

    current = now + timedelta(days=start_day)
    count_days = 0
    while count_days < days_ahead:
        # Skip Sundays (weekday 6)
        if current.weekday() != 6:
            day_str = current.strftime("%A, %b %d, %Y")
            for h in slot_hours:
                slot_start = current.replace(hour=h, minute=0, second=0, microsecond=0)
                if slot_start > now + timedelta(hours=1):
                    slot_end = slot_start + timedelta(minutes=SLOT_DURATION_MINUTES)
                    slots.append(
                        {
                            "start_iso": slot_start.isoformat(),
                            "end_iso": slot_end.isoformat(),
                            "day_label": day_str,
                            "time_label": f"{slot_start.strftime('%I:%M %p')} - {slot_end.strftime('%I:%M %p')}",
                        }
                    )
            count_days += 1
        current += timedelta(days=1)

    return slots


START_NOW = "now"


def validate_requested_slot(start_dt, *, days_ahead: int = 5) -> tuple[datetime, datetime]:
    """Accept only a slot that the portal actually offered; returns (start, end).

    ``start_dt == "now"`` books an immediate interview when INTERVIEW_ALLOW_START_NOW is on.
    """
    if start_dt == START_NOW:
        if not getattr(settings, "INTERVIEW_ALLOW_START_NOW", False):
            raise SchedulingNotAllowed("Starting the interview immediately is not enabled. Please choose a slot.")
        start = timezone.now().replace(microsecond=0)
        return start, start + timedelta(minutes=SLOT_DURATION_MINUTES)
    for slot in generate_available_slots(days_ahead=days_ahead):
        offered = datetime.fromisoformat(slot["start_iso"])
        if offered == start_dt:
            return offered, offered + timedelta(minutes=SLOT_DURATION_MINUTES)
    raise SchedulingNotAllowed("Please choose one of the available interview slots shown on the page.")


def safe_client_ip(request) -> str:
    """Client IP for audit records. X-Forwarded-For is client-controlled, so it is
    only trusted when TRUST_X_FORWARDED_FOR is enabled (behind a known proxy)."""
    candidates = []
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        candidates.append((request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip())
    candidates.append(request.META.get("REMOTE_ADDR") or "")
    for raw in candidates:
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            continue
    return "127.0.0.1"


@transaction.atomic
def schedule_candidate_interview(
    invitation: CandidateInvitation,
    *,
    scheduled_start: datetime,
    scheduled_end: datetime,
    timezone_name: str = "Asia/Karachi",
    room_url: str = "",
) -> InterviewSchedule:
    """Schedule the interview time for a candidate invitation (only before the interview starts)."""
    app = invitation.application
    if interview_has_started(app):
        raise SchedulingNotAllowed("Your interview has already started or finished, so it can no longer be rescheduled.")

    schedule, _ = InterviewSchedule.objects.update_or_create(
        application=app,
        defaults={
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "timezone": timezone_name,
            "room_url": room_url,
            "is_rescheduled": False,
        },
    )

    app.status = "interview_scheduled"
    app.updated_at = timezone.now()
    app.save(update_fields=["status", "updated_at"])

    return schedule


@transaction.atomic
def complete_consent_and_initialize_interview(
    schedule: InterviewSchedule,
    *,
    consent_recording: bool,
    consent_ai_processing: bool,
    ip_address: str,
    user_agent: str,
) -> tuple[InterviewConsent, Interview]:
    """Enforce mandatory candidate consent gate and pre-provision interview & stages."""
    if not consent_recording:
        raise ValueError("Audio and video recording consent is mandatory to proceed with the interview.")
    if not consent_ai_processing:
        raise ValueError("AI automated evaluation consent is mandatory to proceed with the interview.")

    now = timezone.now()
    try:
        safe_ip = str(ipaddress.ip_address((ip_address or "").split(",")[0].strip()))
    except ValueError:
        safe_ip = "127.0.0.1"

    consent, _ = InterviewConsent.objects.update_or_create(
        interview_schedule=schedule,
        defaults={
            "consent_recording": True,
            "consent_ai_processing": True,
            "ip_address": safe_ip,
            "user_agent": (user_agent or "Unknown")[:500],
            "consented_at": now,
        },
    )

    app = schedule.application

    # Pre-create or fetch Interview
    interview, _ = Interview.objects.get_or_create(
        application=app,
        interview_schedule=schedule,
        defaults={
            "status": "pending",
            "media_retention_status": "active",
            "created_at": now,
        },
    )

    # Pre-provision the 3 mandatory stages: screening, technical, behavioral
    stages_config = [
        (1, "screening"),
        (2, "technical"),
        (3, "behavioral"),
    ]
    for order, stype in stages_config:
        InterviewStage.objects.get_or_create(
            interview=interview,
            sequence_order=order,
            defaults={
                "stage_type": stype,
                "status": "not_started",
            },
        )

    # Mark invitation as accepted/used
    invitation = getattr(app, "invitation", None)
    if invitation:
        invitation.is_used = True
        invitation.accepted_at = now
        invitation.save(update_fields=["is_used", "accepted_at"])

    return consent, interview

