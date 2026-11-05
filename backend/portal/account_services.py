from django.utils import timezone

from .models import User

EDITABLE_USER_FIELDS = frozenset(
    {"first_name", "last_name", "phone", "job_title", "work_email", "hr_department"}
)


def update_account_field(user: User, field: str, value: str) -> list[str]:
    if field not in EDITABLE_USER_FIELDS:
        return ["This field cannot be edited here."]

    raw = (value or "").strip()
    errors: list[str] = []

    if field in ("first_name", "last_name", "job_title", "phone") and not raw:
        label = field.replace("_", " ").title()
        errors.append(f"{label} cannot be empty.")
        return errors

    if field == "hr_department":
        setattr(user, field, raw or None)
        user.updated_at = timezone.now()
        user.save(update_fields=[field, "updated_at"])
        return []

    if field == "work_email" and raw:
        if "@" not in raw or "." not in raw.split("@")[-1]:
            errors.append("Enter a valid work email address.")
            return errors
        raw = raw.lower()

    if field == "work_email" and not raw:
        setattr(user, field, None)
    else:
        setattr(user, field, raw)

    if field in ("first_name", "last_name"):
        first = (user.first_name or "").strip()
        last = (user.last_name or "").strip()
        combined = f"{first} {last}".strip()
        if combined:
            user.full_name = combined[:150]

    user.updated_at = timezone.now()
    update_fields = [field, "updated_at"]
    if field in ("first_name", "last_name"):
        update_fields.append("full_name")
    user.save(update_fields=update_fields)
    return []


def account_profile_payload(user: User, company) -> dict:
    from .session_user import build_hr_profile

    return build_hr_profile(user, company)
