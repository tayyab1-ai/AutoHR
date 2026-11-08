"""Register, list, and revoke HR sessions across devices."""

from __future__ import annotations

from django.contrib.sessions.models import Session
from django.utils import timezone

from .session_models import HrUserSession


def _device_label(user_agent: str) -> str:
    ua = (user_agent or "").strip()
    if not ua:
        return "Unknown device"
    if "Windows" in ua:
        platform = "Windows"
    elif "Mac OS" in ua or "Macintosh" in ua:
        platform = "Mac"
    elif "Android" in ua:
        platform = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        platform = "iOS"
    elif "Linux" in ua:
        platform = "Linux"
    else:
        platform = "Browser"
    if "Edg/" in ua:
        browser = "Edge"
    elif "Chrome/" in ua and "Edg/" not in ua:
        browser = "Chrome"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua and "Chrome/" not in ua:
        browser = "Safari"
    else:
        browser = "Web"
    return f"{browser} on {platform}"


def _client_ip(request) -> str | None:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.META.get("REMOTE_ADDR")


def register_hr_session(request, user_id) -> None:
    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    if not session_key:
        return
    ua = request.META.get("HTTP_USER_AGENT", "")
    HrUserSession.objects.update_or_create(
        session_key=session_key,
        defaults={
            "user_id": user_id,
            "device_label": _device_label(ua),
            "user_agent": ua[:2000],
            "ip_address": _client_ip(request),
            "revoked_at": None,
        },
    )


def touch_hr_session(request) -> None:
    session_key = request.session.session_key
    if not session_key:
        return
    HrUserSession.objects.filter(session_key=session_key, revoked_at__isnull=True).update(
        last_seen_at=timezone.now()
    )


def list_hr_sessions(user_id, current_session_key: str | None) -> list[dict]:
    rows = HrUserSession.objects.filter(user_id=user_id, revoked_at__isnull=True).order_by("-last_seen_at")
    out = []
    for row in rows:
        out.append(
            {
                "id": str(row.id),
                "device_label": row.device_label or "Device",
                "ip_address": row.ip_address or "—",
                "created_at": row.created_at.isoformat(),
                "last_seen_at": row.last_seen_at.isoformat(),
                "current": bool(current_session_key and row.session_key == current_session_key),
            }
        )
    return out


def revoke_hr_session(user_id, session_id: str) -> bool:
    row = HrUserSession.objects.filter(id=session_id, user_id=user_id, revoked_at__isnull=True).first()
    if not row:
        return False
    row.revoked_at = timezone.now()
    row.save(update_fields=["revoked_at"])
    Session.objects.filter(session_key=row.session_key).delete()
    return True


def revoke_other_hr_sessions(user_id, current_session_key: str | None) -> int:
    qs = HrUserSession.objects.filter(user_id=user_id, revoked_at__isnull=True)
    if current_session_key:
        qs = qs.exclude(session_key=current_session_key)
    keys = list(qs.values_list("session_key", flat=True))
    if not keys:
        return 0
    Session.objects.filter(session_key__in=keys).delete()
    now = timezone.now()
    return qs.update(revoked_at=now)


def revoke_current_hr_session(request) -> None:
    session_key = request.session.session_key
    if not session_key:
        return
    HrUserSession.objects.filter(session_key=session_key, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
