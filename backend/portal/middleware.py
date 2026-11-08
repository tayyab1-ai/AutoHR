from django.contrib.auth import BACKEND_SESSION_KEY

from .session_services import touch_hr_session

_HR_SESSION_BACKEND = "portal.auth_backend.HrSessionBackend"
_LEGACY_EMAIL_BACKEND = "portal.auth_backend.HrEmailBackend"


class HrLegacySessionMiddleware:
    """Upgrade pre-Google-auth session metadata before AuthenticationMiddleware runs."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        backend = request.session.get(BACKEND_SESSION_KEY)
        if backend == _LEGACY_EMAIL_BACKEND:
            request.session[BACKEND_SESSION_KEY] = _HR_SESSION_BACKEND
            request.session.modified = True
        return self.get_response(request)


class HrSessionActivityMiddleware:
    """Keep last_seen_at fresh for the signed-in device."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and hasattr(user, "db_user"):
            try:
                touch_hr_session(request)
            except Exception:
                pass
        return response
