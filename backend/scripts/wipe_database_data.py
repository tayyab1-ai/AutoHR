"""Truncate all application data (keeps schema and django_migrations). Dev use only."""

import os
import sys

import django

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.db import connection


def main() -> None:
    with connection.cursor() as c:
        c.execute(
            """
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename <> 'django_migrations'
            ORDER BY tablename
            """
        )
        tables = [r[0] for r in c.fetchall()]
        if not tables:
            print("No tables to truncate.")
            return
        quoted = ", ".join(f'"{t}"' for t in tables)
        c.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")
        print(f"Truncated {len(tables)} table(s).")
        for name in tables:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
