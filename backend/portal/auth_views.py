"""Legacy module — logout handlers live in google_auth_views."""

from .google_auth_views import auth_logout_get, auth_logout_view

__all__ = ["auth_logout_view", "auth_logout_get"]
