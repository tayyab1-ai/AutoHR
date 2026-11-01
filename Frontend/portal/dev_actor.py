import os

from django.contrib.auth.hashers import make_password
from django.utils import timezone

from .models import Company, User


def ensure_demo_hr():
    """Ensure the demo company and HR user exist for create-job inserts."""
    email = os.environ.get("DEV_HR_EMAIL", "ayesha.khan@northbridge.pk")
    user = User.objects.filter(email__iexact=email).first()
    if user:
        return user.company, user

    company = Company.objects.create(
        name="Northbridge Technologies",
        website="https://northbridge.pk",
        industry="Software & IT Services",
        company_size="51-200",
        country="Pakistan",
        city="Lahore",
        office_address="3rd Floor, Liberty Tower, Gulberg III",
    )
    now = timezone.now()
    user = User.objects.create(
        company=company,
        email=email,
        full_name="Ayesha Khan",
        password_hash=make_password("demo-hr-password"),
        phone="+92 300 1234567",
        job_title="HR Manager",
        role="hr_manager",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    return company, user
