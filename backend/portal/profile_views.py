import json
import secrets

from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .decorators import hr_login_required
from .google_oauth import authorization_url, email_from_credentials, exchange_code, provider_for_flow, save_credentials
from .profile_services import (
    complete_profile,
    ensure_profile_setup,
    is_profile_complete,
    profile_state,
    save_step1,
    save_step2,
    save_step6,
    save_step_preferences,
)


def _json_body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


@hr_login_required
@require_GET
def profile_state_api(request):
    user = request.user.db_user
    return JsonResponse({"ok": True, **profile_state(user)})


@hr_login_required
@require_POST
def profile_save_step(request, step: int):
    user = request.user.db_user
    setup = ensure_profile_setup(user)
    data = _json_body(request)

    if step == 1:
        errors = save_step1(user, setup, data)
    elif step == 2:
        errors = save_step2(user, setup, data)
    elif step in (3, 4, 5):
        save_step_preferences(setup, step, data)
        errors = []
    elif step == 6:
        errors = save_step6(setup, data)
    elif step == 7:
        errors = complete_profile(user, setup, data)
    else:
        return JsonResponse({"ok": False, "errors": {"step": ["Invalid step."]}}, status=400)

    if errors:
        return JsonResponse({"ok": False, "errors": {"__all__": errors}}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "profile_complete": is_profile_complete(user),
            **profile_state(user),
        }
    )


@hr_login_required
@require_GET
def google_oauth_start(request):
    flow_name = request.GET.get("flow", "gmail")
    if flow_name not in ("gmail", "google_workspace", "google_calendar"):
        return JsonResponse({"ok": False, "errors": {"flow": ["Invalid integration flow."]}}, status=400)
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_flow"] = flow_name
    request.session["google_oauth_user_id"] = str(request.user.db_user.id)
    try:
        url = authorization_url(flow_name, state)
    except RuntimeError:
        return redirect(reverse("dashboard") + "?integration=oauth_not_configured")
    return redirect(url)


@hr_login_required
@require_GET
def google_oauth_callback(request):
    state = request.session.get("google_oauth_state")
    flow_name = request.session.get("google_oauth_flow", "gmail")
    user_id = request.session.get("google_oauth_user_id")
    db_user = request.user.db_user
    if not state or request.GET.get("state") != state:
        return redirect(reverse("dashboard") + "?integration=failed")
    if request.GET.get("error"):
        return redirect(reverse("dashboard") + "?integration=denied")

    code = request.GET.get("code")
    if not code or not user_id:
        return redirect(reverse("dashboard") + "?integration=failed")
    if str(db_user.id) != str(user_id):
        return redirect(reverse("dashboard") + "?integration=failed")

    try:
        creds = exchange_code(flow_name, state, code)
        email = email_from_credentials(creds) or request.GET.get("email", "")
        save_credentials(db_user.id, flow_name, creds, email=email)
        save_step_preferences(
            ensure_profile_setup(request.user.db_user),
            3 if flow_name == "gmail" else (4 if flow_name == "google_workspace" else 5),
            {"oauth_connected": True, "provider": provider_for_flow(flow_name)},
        )
    except Exception:
        return redirect(reverse("dashboard") + "?integration=failed")

    for key in ("google_oauth_state", "google_oauth_flow", "google_oauth_user_id"):
        request.session.pop(key, None)

    return redirect(reverse("dashboard") + "?integration=connected&flow=" + flow_name)
