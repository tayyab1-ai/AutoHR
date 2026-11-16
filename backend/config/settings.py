"""
Django settings for AutoHR.

Layout:
  repo root  — .env, docs, database/
  backend/   — manage.py, config/, portal/ (Django app)
  frontend/  — templates/, static/ (UI assets)
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


def _frontend_dir(root: Path) -> Path:
    """Resolve UI folder (frontend/ or Frontend/ on case-insensitive filesystems)."""
    for name in ("frontend", "Frontend"):
        candidate = root / name
        if (candidate / "templates").is_dir() and (candidate / "static").is_dir():
            return candidate
    return root / "frontend"


FRONTEND_DIR = _frontend_dir(ROOT_DIR)


def _load_dotenv(path, *, override=False):
    """Load KEY=value lines from repo-root .env."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and (override or key not in os.environ):
            os.environ[key] = value


_load_dotenv(ROOT_DIR / ".env", override=True)

def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name, "")
    items = [x.strip() for x in raw.split(",") if x.strip()]
    return items or default


# DEBUG defaults to on for local development; set DJANGO_DEBUG=false on any real server.
DEBUG = _env_bool("DJANGO_DEBUG", True)

# Google returns scopes in a different order than requested; harmless to relax.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
if DEBUG:
    # Plain-HTTP OAuth is only allowed for local development (http://127.0.0.1).
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")
    SECRET_KEY = "dev-only-insecure-key-set-DJANGO_SECRET_KEY-in-env"
if not DEBUG and not TOKEN_ENCRYPTION_KEY:
    raise ImproperlyConfigured("TOKEN_ENCRYPTION_KEY must be set when DJANGO_DEBUG is false.")

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["127.0.0.1", "localhost", "[::1]", "testserver"] if DEBUG else [],
)
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# Only trust X-Forwarded-For when running behind a known reverse proxy.
TRUST_X_FORWARDED_FOR = _env_bool("TRUST_X_FORWARDED_FOR", False)

# Candidates may enter the interview room this many minutes before their slot.
INTERVIEW_ROOM_EARLY_ACCESS_MINUTES = int(os.environ.get("INTERVIEW_ROOM_EARLY_ACCESS_MINUTES", "15"))

# Max request size (audio answers are capped at 20 MB in the view).
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.postgres",
    "django.contrib.staticfiles",
    "portal.apps.PortalConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    *(["config.middleware.DevNoCacheMiddleware"] if DEBUG else []),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "portal.middleware.HrLegacySessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "portal.middleware.HrSessionActivityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "portal.auth_backend.HrSessionBackend",
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    # HTTPS-only cookies and transport on real deployments.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "2592000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    if _env_bool("DJANGO_BEHIND_HTTPS_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "autohr_n"),
        "USER": os.environ.get("POSTGRES_USER", "autohr"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BACKEND_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
