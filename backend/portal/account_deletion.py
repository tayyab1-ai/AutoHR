"""OTP-confirmed account deletion and related data purge."""

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction

from .auth_services import OTP_MAX_ATTEMPTS, OTP_TTL_SECONDS, generate_otp
from .models import Company, JobPosting, JobResponsibility, User
from .profile_models import IntegrationConnection, OAuthCredential, ProfileSetup

DELETE_CACHE_PREFIX = "account_delete:"


def _cache_key(user_id) -> str:
    return DELETE_CACHE_PREFIX + str(user_id)


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


def send_delete_account_email(email: str, otp: str) -> None:
    subject = "Confirm deletion of your AutoHR account"
    message = (
        f"Your account deletion code is: {otp}\n\n"
        f"This code expires in 2 minutes. If you did not request account deletion, "
        f"sign in and change your password immediately.\n\n"
        f"Deleting your account removes your profile, jobs, drafts, and integrations."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email.strip()], fail_silently=False)


def store_delete_pending(user_id, email: str, otp: str) -> None:
    payload = {
        "otp": otp,
        "email": email.strip().lower(),
        "attempts_remaining": OTP_MAX_ATTEMPTS,
    }
    cache.set(_cache_key(user_id), payload, OTP_TTL_SECONDS)


def get_delete_pending(user_id) -> dict | None:
    return cache.get(_cache_key(user_id))


def flush_delete_pending(user_id) -> None:
    cache.delete(_cache_key(user_id))


def issue_account_delete_otp(user: User) -> str:
    otp = generate_otp()
    store_delete_pending(user.id, user.email, otp)
    send_delete_account_email(user.email, otp)
    return otp


@transaction.atomic
def purge_user_account(user: User) -> None:
    """Remove user, company workspace (if sole member), jobs, and integration data."""
    company_id = user.company_id
    user_id = user.id

    sole_company_member = User.objects.filter(company_id=company_id).count() <= 1
    if sole_company_member:
        job_ids = list(JobPosting.objects.filter(company_id=company_id).values_list("id", flat=True))
    else:
        job_ids = list(JobPosting.objects.filter(created_by_id=user_id).values_list("id", flat=True))
    if job_ids:
        JobResponsibility.objects.filter(job_posting_id__in=job_ids).delete()
        JobPosting.objects.filter(id__in=job_ids).delete()

    ProfileSetup.objects.filter(user_id=user_id).delete()
    IntegrationConnection.objects.filter(user_id=user_id).delete()
    OAuthCredential.objects.filter(user_id=user_id).delete()

    other_users = User.objects.filter(company_id=company_id).exclude(id=user_id).count()
    user.delete()
    if other_users == 0:
        Company.objects.filter(id=company_id).delete()

    flush_delete_pending(user_id)
