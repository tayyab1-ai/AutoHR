import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.db import connection

with connection.cursor() as c:
    c.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'users'
          AND column_name = ANY(%s)
        """,
        [["profile_complete", "first_name", "work_email", "accepted_terms_at"]],
    )
    print("users columns:", sorted(r[0] for r in c.fetchall()))
    for table in ("profile_setup", "integration_connections", "oauth_credentials"):
        c.execute("SELECT to_regclass(%s)", [f"public.{table}"])
        print(table, c.fetchone()[0])
