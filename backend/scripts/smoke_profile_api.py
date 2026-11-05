"""Smoke-test profile wizard services (requires at least one user in DB)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from portal.models import User
from portal.profile_services import ensure_profile_setup, profile_state, save_step1

user = User.objects.filter(is_active=True).first()
if not user:
    print("SKIP: no users in database")
    sys.exit(0)

setup = ensure_profile_setup(user)
state = profile_state(user)
assert "step_data" in state and "integrations" in state
errors = save_step1(
    user,
    setup,
    {
        "first_name": "Test",
        "last_name": "HR",
        "phone": "+92 300 0000000",
        "job_title": "HR Manager",
    },
)
assert errors == [], errors
print("OK: profile_state + save_step1 for", user.email)
