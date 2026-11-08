import secrets

from django.contrib.auth import login
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .auth_services import find_or_create_google_user
from .auth_user import HrAuthUser
from .google_oauth import (
    authorization_url,
    exchange_code,
    google_profile_from_credentials,
)
from .session_services import register_hr_session, revoke_current_hr_session


def _safe_next_path(request) -> str:
    nxt = (request.GET.get("next") or request.session.get("auth_next") or "").strip()
    if nxt.startswith("/") and not nxt.startswith("//"):
        return nxt
    return reverse("dashboard")


@require_GET
def google_auth_start(request):
    if getattr(request.user, "is_authenticated", False) and hasattr(request.user, "db_user"):
        return redirect("dashboard")

    state = secrets.token_urlsafe(32)
    request.session["google_auth_state"] = state
    request.session["google_auth_flow"] = "google_auth"
    request.session["auth_next"] = _safe_next_path(request)

    try:
        url, code_verifier = authorization_url("google_auth", state)
    except RuntimeError:
        return redirect(reverse("login") + "?error=oauth_not_configured")
    request.session["google_auth_code_verifier"] = code_verifier
    request.session.modified = True
    request.session.save()
    return redirect(url)


@require_GET
def google_auth_callback(request):
    state = request.session.get("google_auth_state")
    if not state or request.GET.get("state") != state:
        return redirect(reverse("login") + "?error=state_mismatch")

    if request.GET.get("error"):
        return redirect(reverse("login") + "?error=google_denied")

    code = request.GET.get("code")
    if not code:
        return redirect(reverse("login") + "?error=missing_code")

    code_verifier = request.session.get("google_auth_code_verifier")
    try:
        creds = exchange_code("google_auth", state, code, code_verifier=code_verifier)
    except Exception:
        return redirect(reverse("login") + "?error=google_exchange_failed")

    profile = google_profile_from_credentials(creds)

    email = (profile.get("email") or "").strip().lower()
    google_sub = (profile.get("sub") or "").strip()
    full_name = (profile.get("name") or "").strip()

    if not email or not google_sub:
        return redirect(reverse("login") + "?error=google_profile")
    if not profile.get("verified_email", True):
        return redirect(reverse("login") + "?error=email_not_verified")

    try:
        db_user = find_or_create_google_user(email=email, google_sub=google_sub, full_name=full_name)
    except ValueError:
        return redirect(reverse("login") + "?error=signup_failed")

    for key in ("google_auth_state", "google_auth_flow", "google_auth_code_verifier"):
        request.session.pop(key, None)

    hr_user = HrAuthUser(db_user)
    login(request, hr_user, backend="portal.auth_backend.HrSessionBackend")
    register_hr_session(request, db_user.id)

    next_url = request.session.pop("auth_next", None) or reverse("dashboard")
    return redirect(next_url)


@require_POST
def auth_logout_view(request):
    from django.contrib.auth import logout

    revoke_current_hr_session(request)
    logout(request)
    return JsonResponse({"ok": True, "redirect": reverse("landing")})


@require_GET
def auth_logout_get(request):
    from django.contrib.auth import logout

    revoke_current_hr_session(request)
    logout(request)
    return redirect("landing")
