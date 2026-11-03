import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .auth_services import (
    OTP_MAX_ATTEMPTS,
    OTP_TTL_SECONDS,
    apply_password_reset,
    create_user_after_verification,
    email_already_registered,
    flush_password_reset_pending,
    flush_signup_pending,
    get_password_reset_pending,
    get_signup_pending,
    is_valid_password_hash,
    issue_password_reset_otp,
    issue_signup_otp,
    validate_signup_password,
)


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def _form_or_json(request) -> dict:
    if request.content_type and "application/json" in request.content_type:
        return _json_body(request)
    if request.POST:
        return request.POST.dict()
    return _json_body(request)


@require_POST
def signup_send_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("confirm") or ""

    errors = {}
    if not email:
        errors["email"] = ["Email is required."]
    if not password:
        errors["password"] = ["Password is required."]
    if password != confirm:
        errors["confirm_password"] = ["Passwords do not match."]
    pwd_errors = validate_signup_password(password)
    if pwd_errors:
        errors["password"] = pwd_errors
    if email and email_already_registered(email):
        errors["email"] = [
            "An account with this email already exists. Sign in below, or use Forgot password on the login page to set a new password."
        ]

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    try:
        issue_signup_otp(email, password)
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "email": [
                        "Could not send verification email. Check SMTP settings and try again.",
                    ]
                },
            },
            status=502,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "Verification code sent to your email.",
            "expires_in": OTP_TTL_SECONDS,
            "email": email,
        }
    )


@require_POST
def signup_resend_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("confirm") or ""

    if not email or not password:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Session expired. Please sign up again."]}},
            status=400,
        )
    if password != confirm:
        return JsonResponse(
            {"ok": False, "errors": {"confirm_password": ["Passwords do not match."]}},
            status=400,
        )
    if email_already_registered(email):
        return JsonResponse(
            {"ok": False, "errors": {"email": ["This email is already registered."]}},
            status=400,
        )

    try:
        issue_signup_otp(email, password)
    except Exception:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Could not resend code. Check SMTP settings and try again."]}},
            status=502,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "A new verification code has been sent.",
            "expires_in": OTP_TTL_SECONDS,
        }
    )


@require_POST
def signup_verify_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    if not email or not otp:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Email and OTP are required."]}},
            status=400,
        )

    pending = get_signup_pending(email)
    if not pending:
        return JsonResponse(
            {
                "ok": False,
                "errors": {"otp": ["OTP expired or not found. Please sign up again."]},
                "expired": True,
            },
            status=400,
        )

    if otp != pending.get("otp"):
        remaining = int(pending.get("attempts_remaining", OTP_MAX_ATTEMPTS)) - 1
        if remaining <= 0:
            flush_signup_pending(email)
            return JsonResponse(
                {
                    "ok": False,
                    "lockout": True,
                    "message": (
                        "You have entered an incorrect OTP 3 times. Your attempt limit has been reached. "
                        "Please sign up again."
                    ),
                },
                status=403,
            )

        pending["attempts_remaining"] = remaining
        from django.core.cache import cache

        from .auth_services import OTP_TTL_SECONDS, _cache_key

        cache.set(_cache_key(email), pending, OTP_TTL_SECONDS)

        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "otp": [f"Invalid OTP. {remaining} attempt{'s' if remaining != 1 else ''} remaining."]
                },
                "attempts_remaining": remaining,
            },
            status=400,
        )

    if email_already_registered(email):
        flush_signup_pending(email)
        return JsonResponse(
            {"ok": False, "errors": {"email": ["This email is already registered. Please sign in."]}},
            status=400,
        )

    password_hash = pending["password_hash"]
    if not is_valid_password_hash(password_hash):
        flush_signup_pending(email)
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Session error. Please sign up again."]}},
            status=400,
        )

    try:
        create_user_after_verification(email, password_hash)
    except ValueError as exc:
        flush_signup_pending(email)
        return JsonResponse({"ok": False, "errors": {"otp": [str(exc)]}}, status=500)

    flush_signup_pending(email)

    login_url = reverse("login") + "?registered=1"
    return JsonResponse(
        {
            "ok": True,
            "message": "Account verified successfully. You can now sign in.",
            "redirect": login_url,
        }
    )


@require_POST
def auth_login(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return JsonResponse(
            {"ok": False, "errors": {"__all__": ["Email and password are required."]}},
            status=400,
        )

    user = authenticate(request, email=email, password=password)
    if user is None:
        hint = (
            " If you recently registered, use Forgot password to set your password again via email OTP."
            if email_already_registered(email)
            else ""
        )
        return JsonResponse(
            {
                "ok": False,
                "errors": {"__all__": [f"Invalid email or password.{hint}"]},
                "forgot_password": email_already_registered(email),
            },
            status=401,
        )

    # Clear any stale session (e.g. half-written UUID from a prior login attempt).
    if request.session.get("_auth_user_backend") == "portal.auth_backend.HrEmailBackend":
        logout(request)
    elif "_auth_user_id" in request.session:
        request.session.flush()

    login(request, user, backend="portal.auth_backend.HrEmailBackend")
    return JsonResponse(
        {
            "ok": True,
            "message": "Signed in successfully.",
            "redirect": reverse("dashboard"),
        }
    )


@require_POST
def password_reset_send_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("confirm") or ""

    errors = {}
    if not email:
        errors["email"] = ["Email is required."]
    elif not email_already_registered(email):
        errors["email"] = ["No account found for this email. Register first."]
    if not password:
        errors["password"] = ["Password is required."]
    if password != confirm:
        errors["confirm_password"] = ["Passwords do not match."]
    pwd_errors = validate_signup_password(password)
    if pwd_errors:
        errors["password"] = pwd_errors

    if errors:
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    try:
        issue_password_reset_otp(email, password)
    except Exception:
        return JsonResponse(
            {"ok": False, "errors": {"email": ["Could not send reset email. Check SMTP settings."]}},
            status=502,
        )

    return JsonResponse(
        {
            "ok": True,
            "message": "Password reset code sent to your email.",
            "expires_in": OTP_TTL_SECONDS,
            "email": email,
        }
    )


@require_POST
def password_reset_resend_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or data.get("confirm") or ""

    if not email or not password or not email_already_registered(email):
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Session expired. Start forgot password again."]}},
            status=400,
        )
    if password != confirm:
        return JsonResponse(
            {"ok": False, "errors": {"confirm_password": ["Passwords do not match."]}},
            status=400,
        )

    try:
        issue_password_reset_otp(email, password)
    except Exception:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Could not resend code. Try again later."]}},
            status=502,
        )

    return JsonResponse(
        {"ok": True, "message": "A new reset code has been sent.", "expires_in": OTP_TTL_SECONDS}
    )


@require_POST
def password_reset_verify_otp(request):
    data = _form_or_json(request)
    email = (data.get("email") or "").strip().lower()
    otp = (data.get("otp") or "").strip()

    if not email or not otp:
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Email and OTP are required."]}},
            status=400,
        )

    pending = get_password_reset_pending(email)
    if not pending:
        return JsonResponse(
            {
                "ok": False,
                "errors": {"otp": ["Code expired or not found. Request a new reset code."]},
                "expired": True,
            },
            status=400,
        )

    if otp != pending.get("otp"):
        remaining = int(pending.get("attempts_remaining", OTP_MAX_ATTEMPTS)) - 1
        if remaining <= 0:
            flush_password_reset_pending(email)
            return JsonResponse(
                {
                    "ok": False,
                    "lockout": True,
                    "message": "Too many incorrect codes. Start forgot password again.",
                },
                status=403,
            )

        pending["attempts_remaining"] = remaining
        from django.core.cache import cache

        from .auth_services import OTP_TTL_SECONDS, _reset_cache_key

        cache.set(_reset_cache_key(email), pending, OTP_TTL_SECONDS)

        return JsonResponse(
            {
                "ok": False,
                "errors": {
                    "otp": [f"Invalid OTP. {remaining} attempt{'s' if remaining != 1 else ''} remaining."]
                },
                "attempts_remaining": remaining,
            },
            status=400,
        )

    password_hash = pending["password_hash"]
    if not is_valid_password_hash(password_hash) or not apply_password_reset(email, password_hash):
        flush_password_reset_pending(email)
        return JsonResponse(
            {"ok": False, "errors": {"otp": ["Could not update password. Try again."]}},
            status=500,
        )

    flush_password_reset_pending(email)
    return JsonResponse(
        {
            "ok": True,
            "message": "Password updated. You can sign in now.",
            "redirect": reverse("login") + "?reset=1",
        }
    )


@require_POST
def auth_logout_view(request):
    logout(request)
    return JsonResponse({"ok": True, "redirect": reverse("landing")})


@require_GET
def auth_logout_get(request):
    logout(request)
    return redirect("landing")
