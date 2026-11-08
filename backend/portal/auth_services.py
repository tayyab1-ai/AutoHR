"""Google OAuth user provisioning (sign-up / sign-in)."""

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .models import Company, User
from .profile_services import ensure_profile_setup

UNUSABLE_PASSWORD_HASH = make_password(None)


def find_or_create_google_user(*, email: str, google_sub: str, full_name: str) -> User:
    """
    Sign in: match by google_sub, then by email (link sub).
    Sign up: create company + user when no row exists.
    """
    email = email.strip().lower()
    google_sub = google_sub.strip()
    now = timezone.now()

    by_sub = User.objects.filter(google_sub=google_sub, is_active=True).first()
    if by_sub:
        return by_sub

    by_email = User.objects.filter(email__iexact=email, is_active=True).first()
    if by_email:
        other = (
            User.objects.filter(google_sub=google_sub, is_active=True)
            .exclude(pk=by_email.pk)
            .exists()
        )
        if other:
            raise ValueError("This Google account is already linked to another user.")
        User.objects.filter(pk=by_email.pk).update(google_sub=google_sub, updated_at=now)
        by_email.refresh_from_db()
        return by_email

    display_name = (full_name or "").strip()
    if not display_name:
        local = email.split("@")[0].replace(".", " ").replace("_", " ")
        display_name = local.title()[:150] or "New User"
    company_label = f"{display_name.split()[0]} Company"[:200]

    company = Company.objects.create(name=company_label, country="Pakistan")
    user = User.objects.create(
        company=company,
        email=email,
        full_name=display_name[:150],
        google_sub=google_sub,
        password_hash=UNUSABLE_PASSWORD_HASH,
        role="hr_manager",
        is_active=True,
        profile_complete=False,
        created_at=now,
        updated_at=now,
    )
    ensure_profile_setup(user)
    return user
