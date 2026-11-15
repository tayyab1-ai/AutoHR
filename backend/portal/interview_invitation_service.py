"""Interview invitation, magic link generation, email notifications, and candidate scheduling service."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .google_oauth import get_credentials
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
    """Create or refresh an interview invitation magic link for a shortlisted candidate."""
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

    if not created and (invitation.is_expired() or invitation.is_used):
        invitation.magic_token = token
        invitation.expires_at = expires_at
        invitation.is_used = False
        invitation.sent_at = now
        invitation.accepted_at = None
        invitation.save(update_fields=["magic_token", "expires_at", "is_used", "sent_at", "accepted_at"])

    # Update application status
    if application.status != "interview_scheduled":
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

    EmailNotification.objects.create(
        application=application,
        recipient_email=candidate.email,
        notification_type="interview_invite",
        subject=subject,
        body_text=body,
        status="queued",
    )

    return invitation, full_url


def bulk_invite_shortlisted(job: JobPosting, *, base_url: str = "") -> dict[str, Any]:
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
        inv, url = create_or_refresh_candidate_invitation(app, base_url=base_url)
        results.append(
            {
                "application_id": str(app.id),
                "candidate_name": app.candidate.full_name,
                "candidate_email": app.candidate.email,
                "invitation_url": url,
            }
        )

    return {
        "ok": True,
        "invited_count": len(results),
        "candidates": results,
    }


def generate_available_slots(days_ahead: int = 5) -> list[dict[str, Any]]:
    """Generate available interview time slots for self-scheduling."""
    now = timezone.now()
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
                    slot_end = slot_start + timedelta(minutes=45)
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


@transaction.atomic
def schedule_candidate_interview(
    invitation: CandidateInvitation,
    *,
    scheduled_start: datetime,
    scheduled_end: datetime,
    timezone_name: str = "Asia/Karachi",
    room_url: str = "",
) -> InterviewSchedule:
    """Schedule the interview time for a candidate invitation."""
    app = invitation.application

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
    safe_ip = ip_address.split(",")[0].strip() if ip_address else "127.0.0.1"

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

