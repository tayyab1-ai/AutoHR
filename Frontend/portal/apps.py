import uuid

from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"

    def ready(self):
        from django.contrib import auth

        _django_get_user_session_key = auth._get_user_session_key
        _django_aget_user_session_key = auth._aget_user_session_key
        hr_backend = "portal.auth_backend.HrEmailBackend"

        def _get_hr_user_session_key(request):
            backend = request.session.get(auth.BACKEND_SESSION_KEY)
            if backend == hr_backend:
                return uuid.UUID(str(request.session[auth.SESSION_KEY]))
            return _django_get_user_session_key(request)

        async def _aget_hr_user_session_key(request):
            backend = await request.session.aget(auth.BACKEND_SESSION_KEY)
            if backend == hr_backend:
                session_key = await request.session.aget(auth.SESSION_KEY)
                if session_key is None:
                    raise KeyError()
                return uuid.UUID(str(session_key))
            return await _django_aget_user_session_key(request)

        auth._get_user_session_key = _get_hr_user_session_key
        auth._aget_user_session_key = _aget_hr_user_session_key
