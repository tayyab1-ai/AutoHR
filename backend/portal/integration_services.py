"""Integration status and disconnect for Account → Integrations."""

from django.utils import timezone

from .google_oauth import get_credentials
from .profile_models import IntegrationConnection, OAuthCredential
from .profile_services import integration_status


def integrations_account_payload(user_id) -> dict:
    status = integration_status(user_id)
    cred_row = OAuthCredential.objects.filter(user_id=user_id, provider="google_workspace").first()
    token_expires = cred_row.token_expires_at.isoformat() if cred_row and cred_row.token_expires_at else None

    creds = get_credentials(user_id, "google_workspace")
    token_usable = bool(creds and creds.token)

    workspace = status.get("google_workspace") or {}
    meta = workspace.get("metadata") if isinstance(workspace.get("metadata"), dict) else {}

    return {
        "google_workspace": {
            "status": workspace.get("status") or "not_connected",
            "email": workspace.get("email") or "",
            "token_usable": token_usable,
            "token_expires_at": token_expires,
            "spreadsheet_name": meta.get("spreadsheet_name") or "",
            "reconnect_url": "/integrations/google/start/?flow=google_workspace",
        },
        "google_calendar": {
            "status": (status.get("google_calendar") or {}).get("status") or "not_connected",
            "email": (status.get("google_calendar") or {}).get("email") or "",
            "reconnect_url": "/integrations/google/start/?flow=google_calendar",
        },
    }


def disconnect_integration(user_id, provider: str) -> bool:
    if provider not in ("google_workspace", "google_calendar", "gmail"):
        return False
    IntegrationConnection.objects.filter(user_id=user_id, provider=provider).update(
        status="disconnected",
        updated_at=timezone.now(),
    )
    OAuthCredential.objects.filter(user_id=user_id, provider=provider).delete()
    return True
