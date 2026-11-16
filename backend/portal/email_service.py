"""Outbound email delivery through the HR user's connected Gmail account (Gmail API).

AutoHR has no SMTP server. Candidate emails are sent with the ``gmail.send`` scope that
HR grants under Profile -> Integrations -> Gmail. Every attempt is recorded on the
``EmailNotification`` row (status ``sent`` / ``failed`` + error message).
"""

from __future__ import annotations

import base64
import logging
from email.message import EmailMessage
from typing import Any, Iterable

from django.utils import timezone

from .google_oauth import get_credentials
from .models import EmailNotification, User

_logger = logging.getLogger(__name__)

GMAIL_NOT_CONNECTED = (
    "Gmail is not connected for your company. Connect Gmail in Profile -> Integrations "
    "to email candidates automatically, or send the invitation link manually."
)


def _candidate_sender_ids(company, preferred_user_id=None) -> Iterable:
    if preferred_user_id:
        yield preferred_user_id
    for uid in User.objects.filter(company=company).values_list("id", flat=True):
        if uid != preferred_user_id:
            yield uid


def resolve_gmail_credentials(company, preferred_user_id=None):
    """Gmail credentials of the acting HR user, else any HR user of the SAME company."""
    for uid in _candidate_sender_ids(company, preferred_user_id):
        creds = get_credentials(uid, "gmail")
        if creds and creds.token:
            return creds
    return None


def _build_raw_message(to_email: str, subject: str, body_text: str) -> str:
    msg = EmailMessage()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)  # Gmail sets From to the authenticated HR address
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


def deliver_notification(notification: EmailNotification, *, company, sender_user_id=None) -> dict[str, Any]:
    """Send a queued EmailNotification via Gmail. Never raises; returns {sent, error}."""
    creds = resolve_gmail_credentials(company, sender_user_id)
    if not creds:
        notification.status = "failed"
        notification.error_message = GMAIL_NOT_CONNECTED
        notification.save(update_fields=["status", "error_message"])
        return {"sent": False, "error": GMAIL_NOT_CONNECTED}

    try:
        from googleapiclient.discovery import build

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        raw = _build_raw_message(
            notification.recipient_email,
            notification.subject,
            notification.body_text,
        )
        result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    except Exception as exc:  # HttpError, network, token refresh
        _logger.warning("Gmail send failed for notification %s: %s", notification.id, exc)
        error = f"Gmail could not send the email: {exc}"
        notification.status = "failed"
        notification.error_message = error[:2000]
        notification.save(update_fields=["status", "error_message"])
        return {"sent": False, "error": error}

    notification.status = "sent"
    notification.sent_at = timezone.now()
    notification.external_provider_id = str(result.get("id") or "")[:255]
    notification.error_message = None
    notification.save(update_fields=["status", "sent_at", "external_provider_id", "error_message"])
    return {"sent": True, "error": None}
