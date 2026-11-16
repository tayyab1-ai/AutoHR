import uuid

from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"

    def ready(self):
        from django.contrib import auth

        _django_get_user_session_key = auth._get_user_session_key
        _django_aget_user_session_key = auth._aget_user_session_key
        _hr_backends = {
            "portal.auth_backend.HrSessionBackend",
            "portal.auth_backend.HrEmailBackend",
        }

        def _parse_session_user_id(raw):
            try:
                return uuid.UUID(str(raw))
            except (ValueError, AttributeError, TypeError):
                return None

        def _get_hr_user_session_key(request):
            backend = request.session.get(auth.BACKEND_SESSION_KEY)
            raw = request.session.get(auth.SESSION_KEY)
            if backend in _hr_backends and raw is not None:
                parsed = _parse_session_user_id(raw)
                if parsed is not None:
                    return parsed
                raise KeyError()
            if raw is not None:
                parsed = _parse_session_user_id(raw)
                if parsed is not None:
                    return parsed
            return _django_get_user_session_key(request)

        async def _aget_hr_user_session_key(request):
            backend = await request.session.aget(auth.BACKEND_SESSION_KEY)
            session_key = await request.session.aget(auth.SESSION_KEY)
            if backend in _hr_backends and session_key is not None:
                parsed = _parse_session_user_id(session_key)
                if parsed is not None:
                    return parsed
            if session_key is not None:
                parsed = _parse_session_user_id(session_key)
                if parsed is not None:
                    return parsed
            return await _django_aget_user_session_key(request)

        auth._get_user_session_key = _get_hr_user_session_key
        auth._aget_user_session_key = _aget_hr_user_session_key

        from .background_sync import start_background_form_sync

        start_background_form_sync()
