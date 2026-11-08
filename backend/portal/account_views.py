import json

from django.contrib.auth import logout
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .account_deletion import purge_user_account
from .account_services import account_profile_payload, update_account_field
from .decorators import hr_login_required
from .integration_services import disconnect_integration, integrations_account_payload
from .session_services import list_hr_sessions, revoke_hr_session, revoke_other_hr_sessions, revoke_current_hr_session


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
@require_GET
def account_integrations_api(request):
    user = request.user.db_user
    return JsonResponse({"ok": True, "integrations": integrations_account_payload(user.id)})


@hr_login_required
@require_POST
def account_disconnect_integration(request):
    user = request.user.db_user
    data = _json_body(request)
    provider = (data.get("provider") or "").strip()
    if not disconnect_integration(user.id, provider):
        return JsonResponse(
            {"ok": False, "errors": {"provider": ["Unknown or invalid integration."]}},
            status=400,
        )
    return JsonResponse(
        {
            "ok": True,
            "message": "Disconnected. Connect again to issue new permissions.",
            "integrations": integrations_account_payload(user.id),
        }
    )


@hr_login_required
@require_GET
def account_sessions_api(request):
    user = request.user.db_user
    session_key = request.session.session_key
    sessions = list_hr_sessions(user.id, session_key)
    return JsonResponse({"ok": True, "sessions": sessions})


@hr_login_required
@require_POST
def account_revoke_session(request):
    user = request.user.db_user
    data = _json_body(request)
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return JsonResponse({"ok": False, "errors": {"session_id": ["Required."]}}, status=400)
    if not revoke_hr_session(user.id, session_id):
        return JsonResponse({"ok": False, "errors": {"session_id": ["Session not found."]}}, status=404)
    return JsonResponse({"ok": True, "message": "Device signed out.", "sessions": list_hr_sessions(user.id, request.session.session_key)})


@hr_login_required
@require_POST
def account_revoke_other_sessions(request):
    user = request.user.db_user
    count = revoke_other_hr_sessions(user.id, request.session.session_key)
    return JsonResponse(
        {
            "ok": True,
            "message": f"Signed out {count} other device(s)." if count else "No other active sessions.",
            "sessions": list_hr_sessions(user.id, request.session.session_key),
        }
    )


@hr_login_required
@require_POST
def account_delete_confirm(request):
    user = request.user.db_user
    data = _json_body(request)
    confirmation = (data.get("confirmation") or "").strip()
    email = (data.get("email") or "").strip().lower()

    if confirmation != "DELETE":
        return JsonResponse(
            {"ok": False, "errors": {"confirmation": ['Type DELETE (all caps) to confirm.']}},
            status=400,
        )
    if email != user.email.strip().lower():
        return JsonResponse(
            {"ok": False, "errors": {"email": ["Email must match your account email exactly."]}},
            status=400,
        )

    purge_user_account(user)
    revoke_current_hr_session(request)
    logout(request)
    return JsonResponse(
        {
            "ok": True,
            "message": "Your account and workspace data have been deleted.",
            "redirect": reverse("landing"),
        }
    )
