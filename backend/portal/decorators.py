from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect


def hr_login_required(view_func):
    """Require a signed-in HR user (portal session). JSON/API requests get 401 + login redirect hint."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False) or not hasattr(user, "db_user"):
            if request.method != "GET" or "application/json" in (request.headers.get("Accept") or ""):
                return JsonResponse(
                    {
                        "ok": False,
                        "errors": {"auth": ["Sign in required."]},
                        "redirect": settings.LOGIN_URL,
                    },
                    status=401,
                )
            login_url = settings.LOGIN_URL
            next_path = request.get_full_path()
            if next_path and next_path != login_url:
                return redirect(f"{login_url}?next={next_path}")
            return redirect(login_url)
        return view_func(request, *args, **kwargs)

    return _wrapped
