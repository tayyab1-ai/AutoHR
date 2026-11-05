import json

from django.contrib.auth import logout
from django.core.cache import cache
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .account_deletion import (
    flush_delete_pending,
    get_delete_pending,
    issue_account_delete_otp,
    mask_email,
    purge_user_account,
)
from .account_services import account_profile_payload, update_account_field
from .auth_services import OTP_MAX_ATTEMPTS, OTP_TTL_SECONDS
from .decorators import hr_login_required


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


@hr_login_required
@require_GET
def account_profile_api(request):
    user = request.user.db_user
    company = user.company
    return JsonResponse({"ok": True, "profile": account_profile_payload(user, company)})


@hr_login_required
@require_POST
def account_update_field(request):
    user = request.user.db_user
    data = _json_body(request)
    field = (data.get("field") or "").strip()
    value = data.get("value")
    if value is not None and not isinstance(value, str):
        value = str(value)

    errors = update_account_field(user, field, value or "")
    if errors:
        return JsonResponse({"ok": False, "errors": {"__all__": errors}}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "message": "Saved successfully.",
            "profile": account_profile_payload(user, user.company),
        }
    )


@hr_login_required
@require_POST
def account_delete_send_otp(request):
    user = request.user.db_user
    try:
        issue_account_delete_otp(user)
    except Exception:
        return JsonResponse(
            {"ok": False, "errors": {"email": ["Could not send verification code. Try again later."]}},
            status=502,
        )
    return JsonResponse(
        {
            "ok": True,
            "message": "Verification code sent to your account email.",
            "expires_in": OTP_TTL_SECONDS,
            "email_masked": mask_email(user.email),
        }
    )


@hr_login_required
@require_POST
def account_delete_resend_otp(request):
    user = request.user.db_user
    pending = get_delete_pending(user.id)
    if not pending:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["No active deletion request. Start again."]}, "expired": True},
            status=400,
        )
    try:
        issue_account_delete_otp(user)
    except Exception:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Could not resend code. Try again later."]}},
            status=502,
        )
    return JsonResponse(
        {"ok": True, "message": "A new code has been sent.", "expires_in": OTP_TTL_SECONDS}
    )


@hr_login_required
@require_POST
def account_delete_verify(request):
    user = request.user.db_user
    data = _json_body(request)
    otp = (data.get("otp") or "").strip()

    if not otp:
        return JsonResponse({"ok": False, "errors": {"otp": ["Enter the 6-digit code."]}}, status=400)

    pending = get_delete_pending(user.id)
    if not pending:
        return JsonResponse(
            {
                "ok": False,
                "errors": {"otp": ["Code expired or not found. Request a new code."]},
                "expired": True,
            },
            status=400,
        )

    if pending.get("email") != user.email.strip().lower():
        flush_delete_pending(user.id)
        return JsonResponse({"ok": False, "errors": {"otp": ["Session mismatch. Start again."]}}, status=403)

    if otp != pending.get("otp"):
        remaining = int(pending.get("attempts_remaining", OTP_MAX_ATTEMPTS)) - 1
        if remaining <= 0:
            flush_delete_pending(user.id)
            return JsonResponse(
                {
                    "ok": False,
                    "lockout": True,
                    "message": "Too many incorrect codes. Request a new deletion code.",
                },
                status=403,
            )
        pending["attempts_remaining"] = remaining
        from .account_deletion import _cache_key

        cache.set(_cache_key(user.id), pending, OTP_TTL_SECONDS)
        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "otp": [f"Invalid code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."]
                },
                "attempts_remaining": remaining,
            },
            status=400,
        )

    db_user = user
    purge_user_account(db_user)
    logout(request)
    return JsonResponse(
        {
            "ok": True,
            "message": "Your account and workspace data have been deleted.",
            "redirect": reverse("landing"),
        }
    )
