"""
Django settings for AutoHR.

Layout:
  repo root  — .env, docs, database/
  backend/   — manage.py, config/, portal/ (Django app)
  frontend/  — templates/, static/ (UI assets)
"""

import os
from pathlib import Path

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

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "dev-only-secret-key-for-autohr-frontend-demo-change-me",
)

TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY", "")

DEBUG = True

ALLOWED_HOSTS = ["*"]

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
    "config.middleware.DevNoCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "portal.auth_backend.HrEmailBackend",
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "autohr-auth-otp",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER") or os.environ.get("EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD") or os.environ.get("EMAIL_PASS", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "noreply@autohr.local")

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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
