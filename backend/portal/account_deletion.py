"""Account deletion and workspace purge (after in-app confirmation)."""

from django.db import transaction

from .models import Company, JobPosting, JobResponsibility, User
from .profile_models import IntegrationConnection, OAuthCredential, ProfileSetup


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

    from .session_models import HrUserSession

    HrUserSession.objects.filter(user_id=user_id).delete()

    other_users = User.objects.filter(company_id=company_id).exclude(id=user_id).count()
    user.delete()
    if other_users == 0:
        Company.objects.filter(id=company_id).delete()
