from django.utils import timezone

from .models import Company, User
from .profile_models import IntegrationConnection, ProfileSetup


def ensure_profile_setup(user: User) -> ProfileSetup:
    setup, _ = ProfileSetup.objects.get_or_create(
        user_id=user.id,
        defaults={"company_id": user.company_id, "current_step": 1},
    )
    return setup


def is_profile_complete(user: User) -> bool:
    if getattr(user, "profile_complete", False):
        return True
    setup = ProfileSetup.objects.filter(user_id=user.id).first()
    return bool(setup and setup.profile_complete)


def integration_status(user_id) -> dict:
    rows = IntegrationConnection.objects.filter(user_id=user_id)
    out = {}
    for r in rows:
        out[r.provider] = {
            "status": r.status,
            "email": r.connected_email or "",
            "metadata": r.metadata or {},
        }
    for key in ("gmail", "google_workspace", "google_calendar"):
        out.setdefault(key, {"status": "not_connected", "email": "", "metadata": {}})
    return out


def mark_step_complete(setup: ProfileSetup, step: int) -> None:
    steps = list(setup.completed_steps or [])
    if step not in steps:
        steps.append(step)
        steps.sort()
    setup.completed_steps = steps
    setup.current_step = min(step + 1, 7)
    setup.save(update_fields=["completed_steps", "current_step", "updated_at"])


def save_step1(user: User, setup: ProfileSetup, data: dict) -> list[str]:
    errors = []
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    job_title = (data.get("job_title") or data.get("job_designation") or "").strip()
    work_email = (data.get("work_email") or "").strip().lower()
    department = (data.get("hr_department") or "").strip()

    if not first:
        errors.append("First name is required.")
    if not last:
        errors.append("Last name is required.")
    if not phone:
        errors.append("Phone number is required.")
    if not job_title:
        errors.append("Job designation is required.")
    if errors:
        return errors

    user.first_name = first
    user.last_name = last
    user.full_name = f"{first} {last}"[:150]
    user.phone = phone
    user.job_title = job_title
    user.work_email = work_email or None
    user.hr_department = department or None
    user.updated_at = timezone.now()
    user.save(
        update_fields=[
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "job_title",
            "work_email",
            "hr_department",
            "updated_at",
        ]
    )

    step_data = setup.step_data or {}
    step_data["1"] = {
        "first_name": first,
        "last_name": last,
        "account_email": user.email,
        "work_email": work_email,
        "phone": phone,
        "job_title": job_title,
        "hr_department": department,
    }
    setup.step_data = step_data
    setup.save(update_fields=["step_data", "updated_at"])
    mark_step_complete(setup, 1)
    return []


def save_step2(user: User, setup: ProfileSetup, data: dict) -> list[str]:
    errors = []
    name = (data.get("company_name") or "").strip()
    website = (data.get("company_website") or "").strip()
    industry = (data.get("industry") or "").strip()
    size = (data.get("company_size") or "").strip()
    ctype = (data.get("company_type") or "").strip()
    desc = (data.get("company_description") or "").strip()
    founded = data.get("founded_year")
    address = (data.get("office_address") or "").strip()
    linkedin = (data.get("company_linkedin_url") or "").strip()

    if not name:
        errors.append("Company name is required.")
    if not website:
        errors.append("Company website is required.")
    if not industry:
        errors.append("Industry is required.")
    if not size:
        errors.append("Company size is required.")
    if not ctype:
        errors.append("Company type is required.")
    if not desc:
        errors.append("Company description is required.")
    if errors:
        return errors

    company = user.company
    company.name = name
    company.website = website
    company.industry = industry
    company.company_size = size
    company.company_type = ctype
    company.description = desc
    company.office_address = address or None
    company.linkedin_profile_url = linkedin or None
    if founded not in (None, ""):
        try:
            company.founded_year = int(founded)
        except (TypeError, ValueError):
            errors.append("Founded year must be a number.")
            return errors
    company.updated_at = timezone.now()
    company.save(
        update_fields=[
            "name",
            "website",
            "industry",
            "company_size",
            "company_type",
            "description",
            "office_address",
            "linkedin_profile_url",
            "founded_year",
            "updated_at",
        ]
    )

    step_data = setup.step_data or {}
    step_data["2"] = data
    setup.step_data = step_data
    setup.save(update_fields=["step_data", "updated_at"])
    mark_step_complete(setup, 2)
    return []


def save_step6(setup: ProfileSetup, data: dict) -> list[str]:
    errors = []
    name = (data.get("sender_display_name") or "").strip()
    if not name:
        errors.append("Sender display name is required.")
    if errors:
        return errors
    save_step_preferences(setup, 6, data)
    return []


def save_step_preferences(setup: ProfileSetup, step: int, data: dict) -> None:
    step_data = setup.step_data or {}
    step_data[str(step)] = data
    setup.step_data = step_data
    setup.save(update_fields=["step_data", "updated_at"])
    mark_step_complete(setup, step)


def complete_profile(user: User, setup: ProfileSetup, data: dict) -> list[str]:
    errors = []
    if not data.get("accept_terms"):
        errors.append("You must accept the Terms & Conditions.")
    if not data.get("accept_privacy"):
        errors.append("You must accept the Privacy Policy.")
    required_steps = {1, 2, 6}
    done = set(setup.completed_steps or [])
    if not required_steps.issubset(done):
        errors.append("Complete all required wizard steps before finishing.")
    if errors:
        return errors

    now = timezone.now()
    user.profile_complete = True
    user.accepted_terms_at = now
    user.accepted_privacy_at = now
    user.updated_at = now
    user.save(
        update_fields=["profile_complete", "accepted_terms_at", "accepted_privacy_at", "updated_at"]
    )

    setup.profile_complete = True
    setup.current_step = 7
    step_data = setup.step_data or {}
    step_data["7"] = data
    setup.step_data = step_data
    if 7 not in (setup.completed_steps or []):
        mark_step_complete(setup, 7)
    else:
        setup.save(update_fields=["step_data", "profile_complete", "current_step", "updated_at"])
    return []


def _hydrated_step_data(user: User, setup: ProfileSetup) -> dict:
    """Merge DB user/company fields so the wizard can repopulate after refresh."""
    step_data = dict(setup.step_data or {})
    step1 = dict(step_data.get("1") or {})
    if not step1.get("first_name") and getattr(user, "first_name", None):
        step1["first_name"] = user.first_name
    if not step1.get("last_name") and getattr(user, "last_name", None):
        step1["last_name"] = user.last_name
    if not step1.get("phone") and user.phone:
        step1["phone"] = user.phone
    if not step1.get("job_title") and user.job_title:
        step1["job_title"] = user.job_title
    if not step1.get("work_email") and getattr(user, "work_email", None):
        step1["work_email"] = user.work_email
    if not step1.get("hr_department") and getattr(user, "hr_department", None):
        step1["hr_department"] = user.hr_department
    step1.setdefault("account_email", user.email)
    if step1:
        step_data["1"] = step1

    company = user.company
    step2 = dict(step_data.get("2") or {})
    if not step2.get("company_name") and company.name:
        step2["company_name"] = company.name
    if not step2.get("company_website") and company.website:
        step2["company_website"] = company.website
    if not step2.get("industry") and company.industry:
        step2["industry"] = company.industry
    if not step2.get("company_size") and company.company_size:
        step2["company_size"] = company.company_size
    if not step2.get("company_type") and getattr(company, "company_type", None):
        step2["company_type"] = company.company_type
    if not step2.get("company_description") and getattr(company, "description", None):
        step2["company_description"] = company.description
    if not step2.get("office_address") and company.office_address:
        step2["office_address"] = company.office_address
    if not step2.get("company_linkedin_url") and company.linkedin_profile_url:
        step2["company_linkedin_url"] = company.linkedin_profile_url
    if step2.get("founded_year") in (None, "") and getattr(company, "founded_year", None):
        step2["founded_year"] = company.founded_year
    if step2:
        step_data["2"] = step2
    return step_data


def profile_state(user: User) -> dict:
    setup = ensure_profile_setup(user)
    return {
        "profile_complete": is_profile_complete(user),
        "current_step": setup.current_step,
        "completed_steps": setup.completed_steps or [],
        "step_data": _hydrated_step_data(user, setup),
        "integrations": integration_status(user.id),
        "account_email": user.email,
    }
