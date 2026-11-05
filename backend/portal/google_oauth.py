import os
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from .encryption import decrypt_text, encrypt_text
from .profile_models import IntegrationConnection, OAuthCredential

GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
]

WORKSPACE_SCOPES = GMAIL_SCOPES + [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

CALENDAR_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def _client_config() -> dict:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("Google OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env.")
    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/integrations/google/callback/",
    )


def scopes_for_flow(flow_name: str) -> list[str]:
    if flow_name == "gmail":
        return GMAIL_SCOPES
    if flow_name == "google_workspace":
        return WORKSPACE_SCOPES
    if flow_name == "google_calendar":
        return CALENDAR_SCOPES
    return GMAIL_SCOPES


def provider_for_flow(flow_name: str) -> str:
    if flow_name == "gmail":
        return "gmail"
    if flow_name == "google_workspace":
        return "google_workspace"
    if flow_name == "google_calendar":
        return "google_calendar"
    return "gmail"


def build_flow(flow_name: str, state: str) -> Flow:
    flow = Flow.from_client_config(
        _client_config(),
        scopes=scopes_for_flow(flow_name),
        state=state,
        redirect_uri=redirect_uri(),
    )
    return flow


def authorization_url(flow_name: str, state: str) -> str:
    flow = build_flow(flow_name, state)
    url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url


def exchange_code(flow_name: str, state: str, code: str):
    flow = build_flow(flow_name, state)
    flow.fetch_token(code=code)
    return flow.credentials


def email_from_credentials(creds: Credentials) -> str:
    """Resolve the Google account email after OAuth (userinfo scope)."""
    try:
        from googleapiclient.discovery import build

        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        info = service.userinfo().get().execute()
        return (info.get("email") or "").strip()
    except Exception:
        return ""


def save_credentials(user_id, flow_name: str, creds: Credentials, email: str = "") -> None:
    provider = provider_for_flow(flow_name)
    expires = creds.expiry
    if expires and timezone.is_naive(expires):
        expires = timezone.make_aware(expires)

    OAuthCredential.objects.update_or_create(
        user_id=user_id,
        provider=provider,
        defaults={
            "access_token_enc": encrypt_text(creds.token or ""),
            "refresh_token_enc": encrypt_text(creds.refresh_token or ""),
            "token_expires_at": expires,
        },
    )
    IntegrationConnection.objects.update_or_create(
        user_id=user_id,
        provider=provider,
        defaults={
            "status": "connected",
            "connected_email": email or "",
            "scopes": list(creds.scopes or scopes_for_flow(flow_name)),
        },
    )


def get_credentials(user_id, provider: str) -> Credentials | None:
    row = OAuthCredential.objects.filter(user_id=user_id, provider=provider).first()
    if not row or not row.access_token_enc:
        return None
    token = decrypt_text(row.access_token_enc)
    refresh = decrypt_text(row.refresh_token_enc or "")
    return Credentials(
        token=token,
        refresh_token=refresh or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=scopes_for_flow(provider if provider != "gmail" else "gmail"),
    )
