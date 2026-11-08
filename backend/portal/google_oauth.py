import os
from datetime import timedelta

from django.utils import timezone as django_tz

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

from django.conf import settings
from django.utils import timezone
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from .encryption import decrypt_text, encrypt_text
from .profile_models import IntegrationConnection, OAuthCredential

AUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
]

WORKSPACE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
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


def integration_redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/integrations/google/callback/",
    )


def auth_redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_AUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/auth/google/callback/",
    )


def redirect_uri() -> str:
    """Backward-compatible alias for integration OAuth."""
    return integration_redirect_uri()


def redirect_uri_for(flow_name: str) -> str:
    if flow_name == "google_auth":
        return auth_redirect_uri()
    return integration_redirect_uri()


def scopes_for_flow(flow_name: str) -> list[str]:
    if flow_name == "google_auth":
        return AUTH_SCOPES
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


def build_flow(flow_name: str, state: str, *, code_verifier: str | None = None) -> Flow:
    flow_kwargs = {}
    if code_verifier:
        flow_kwargs["code_verifier"] = code_verifier
        flow_kwargs["autogenerate_code_verifier"] = False
    flow = Flow.from_client_config(
        _client_config(),
        scopes=scopes_for_flow(flow_name),
        state=state,
        redirect_uri=redirect_uri_for(flow_name),
        **flow_kwargs,
    )
    return flow


def authorization_url(flow_name: str, state: str) -> tuple[str, str]:
    """Return (redirect_url, pkce_code_verifier). Store verifier in session until callback."""
    flow = build_flow(flow_name, state)
    kwargs = {
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    if flow_name != "google_auth":
        kwargs["prompt"] = "consent"
    url, _ = flow.authorization_url(**kwargs)
    if not flow.code_verifier:
        raise RuntimeError("OAuth PKCE code_verifier was not generated.")
    return url, flow.code_verifier


def exchange_code(flow_name: str, state: str, code: str, *, code_verifier: str | None = None):
    if not code_verifier:
        raise ValueError("Missing PKCE code_verifier for token exchange.")
    flow = build_flow(flow_name, state, code_verifier=code_verifier)
    flow.fetch_token(code=code)
    return flow.credentials


def _profile_from_id_token(creds: Credentials) -> dict:
    token = getattr(creds, "id_token", None)
    if not token:
        return {}
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        info = google_id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        return {
            "email": (info.get("email") or "").strip().lower(),
            "sub": str(info.get("sub") or "").strip(),
            "name": (info.get("name") or "").strip(),
            "verified_email": bool(info.get("email_verified", True)),
        }
    except Exception:
        return {}


def google_profile_from_credentials(creds: Credentials) -> dict:
    """Email, Google subject id, and display name (id_token first, then userinfo API)."""
    profile = _profile_from_id_token(creds)
    if profile.get("email") and profile.get("sub"):
        return profile

    try:
        from googleapiclient.discovery import build

        service = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        info = service.userinfo().get().execute()
        return {
            "email": (info.get("email") or "").strip().lower(),
            "sub": str(info.get("id") or "").strip(),
            "name": (info.get("name") or "").strip(),
            "verified_email": bool(info.get("verified_email", True)),
        }
    except Exception:
        return profile


def email_from_credentials(creds: Credentials) -> str:
    return google_profile_from_credentials(creds).get("email") or ""


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


def _scopes_for_provider(provider: str) -> list[str]:
    if provider == "google_workspace":
        return WORKSPACE_SCOPES
    if provider == "google_calendar":
        return CALENDAR_SCOPES
    if provider == "gmail":
        return GMAIL_SCOPES
    return WORKSPACE_SCOPES


def _persist_refreshed_tokens(user_id, provider: str, creds: Credentials) -> None:
    expires = creds.expiry
    if expires and timezone.is_naive(expires):
        expires = timezone.make_aware(expires)
    OAuthCredential.objects.filter(user_id=user_id, provider=provider).update(
        access_token_enc=encrypt_text(creds.token or ""),
        refresh_token_enc=encrypt_text(creds.refresh_token or ""),
        token_expires_at=expires,
        updated_at=timezone.now(),
    )


def get_credentials(user_id, provider: str) -> Credentials | None:
    row = OAuthCredential.objects.filter(user_id=user_id, provider=provider).first()
    if not row or not row.access_token_enc:
        return None
    token = decrypt_text(row.access_token_enc)
    refresh = decrypt_text(row.refresh_token_enc or "")
    conn = IntegrationConnection.objects.filter(user_id=user_id, provider=provider).first()
    scope_list = list(conn.scopes) if conn and conn.scopes else _scopes_for_provider(provider)
    creds = Credentials(
        token=token,
        refresh_token=refresh or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=scope_list,
    )
    if row.token_expires_at:
        creds.expiry = row.token_expires_at

    stale = False
    if row.token_expires_at and row.token_expires_at <= django_tz.now() + timedelta(minutes=3):
        stale = True

    try:
        from google.auth.transport.requests import Request

        if (stale or not creds.valid) and creds.refresh_token:
            creds.refresh(Request())
            _persist_refreshed_tokens(user_id, provider, creds)
    except Exception:
        if stale:
            return None
    return creds
