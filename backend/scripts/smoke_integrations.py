"""Import and catalog sanity checks (no Google API calls)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from portal.form_catalog import default_selected_field_keys, field_by_key, FORM_SECTIONS
from portal.form_config_services import save_job_form_config
from portal.profile_services import save_step3

assert len(FORM_SECTIONS) == 6
keys = default_selected_field_keys()
assert len(keys) >= 20
assert field_by_key("full_name") is not None

# save_step3 validation without DB user — logic-only
class _Setup:
    step_data = {}
    completed_steps = []

class _User:
    id = "00000000-0000-0000-0000-000000000099"
    company_id = "00000000-0000-0000-0000-000000000098"

errs = save_step3(_User(), _Setup(), {})
assert any("Connect your Google account" in e for e in errs)

print("OK: form catalog and save_step3 validation")
