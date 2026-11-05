import re
import secrets

from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings

from .models import Company, User

OTP_TTL_SECONDS = 120
OTP_MAX_ATTEMPTS = 3
OTP_CACHE_PREFIX = "signup_otp:"
RESET_CACHE_PREFIX = "password_reset:"


def _cache_key(email: str) -> str:
    return OTP_CACHE_PREFIX + email.strip().lower()


def validate_signup_password(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Za-z]", password):
        errors.append("Password must include at least one letter.")
    if not re.search(r"\d", password):
        errors.append("Password must include at least one number.")
    return errors


def email_already_registered(email: str) -> bool:
    return User.objects.filter(email__iexact=email.strip()).exists()


def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def send_otp_email(email: str, otp: str) -> None:
    subject = "Your AutoHR verification code"
    message = (
        f"Your verification code is: {otp}\n\n"
        f"This code expires in 2 minutes. If you did not request this, ignore this email."
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email.strip()],
        fail_silently=False,
    )


def store_signup_pending(email: str, password: str, otp: str) -> None:
    payload = {
        "otp": otp,
        "password_hash": make_password(password),
        "attempts_remaining": OTP_MAX_ATTEMPTS,
    }
    cache.set(_cache_key(email), payload, OTP_TTL_SECONDS)


def get_signup_pending(email: str) -> dict | None:
    return cache.get(_cache_key(email))


def flush_signup_pending(email: str) -> None:
    cache.delete(_cache_key(email))


def issue_signup_otp(email: str, password: str) -> str:
    otp = generate_otp()
    store_signup_pending(email, password, otp)
    send_otp_email(email, otp)
    return otp


def _reset_cache_key(email: str) -> str:
    return RESET_CACHE_PREFIX + email.strip().lower()


def store_password_reset_pending(email: str, password: str, otp: str) -> None:
    payload = {
        "otp": otp,
        "password_hash": make_password(password),
        "attempts_remaining": OTP_MAX_ATTEMPTS,
    }
    cache.set(_reset_cache_key(email), payload, OTP_TTL_SECONDS)


def get_password_reset_pending(email: str) -> dict | None:
    return cache.get(_reset_cache_key(email))


def flush_password_reset_pending(email: str) -> None:
    cache.delete(_reset_cache_key(email))


def send_password_reset_email(email: str, otp: str) -> None:
    subject = "Your AutoHR password reset code"
    message = (
        f"Your password reset code is: {otp}\n\n"
        f"This code expires in 2 minutes. If you did not request this, ignore this email."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email.strip()], fail_silently=False)


def issue_password_reset_otp(email: str, password: str) -> str:
    otp = generate_otp()
    store_password_reset_pending(email, password, otp)
    send_password_reset_email(email, otp)
    return otp


def apply_password_reset(email: str, password_hash: str) -> bool:
    from django.utils import timezone

    email = email.strip().lower()
    updated = User.objects.filter(email__iexact=email, is_active=True).update(
        password_hash=password_hash,
        updated_at=timezone.now(),
    )
    return updated > 0


def create_user_after_verification(email: str, password_hash: str) -> User:
    """Create placeholder company + HR user after OTP verified."""
    from django.utils import timezone

    email = email.strip().lower()
    local = email.split("@")[0].replace(".", " ").replace("_", " ")
    display_name = local.title()[:150] or "New User"
    company_label = f"{display_name.split()[0]} Company"[:200]

    now = timezone.now()
    company = Company.objects.create(
        name=company_label,
        country="Pakistan",
    )
    user = User.objects.create(
        company=company,
        email=email,
        full_name=display_name,
        password_hash=password_hash,
        role="hr_manager",
        is_active=True,
        profile_complete=False,
        created_at=now,
        updated_at=now,
    )
    from .profile_services import ensure_profile_setup

    ensure_profile_setup(user)
    user.refresh_from_db()
    if not is_valid_password_hash(user.password_hash):
        user.delete()
        company.delete()
        raise ValueError("Account could not be saved securely. Please sign up again.")
    return user


def is_valid_password_hash(stored: str) -> bool:
    """Ensure hash looks complete (guards against DB truncation or corrupt saves)."""
    from django.contrib.auth.hashers import identify_hasher

    h = (stored or "").strip()
    if len(h) < 20:
        return False
    try:
        identify_hasher(h)
    except ValueError:
        return False
    return True
