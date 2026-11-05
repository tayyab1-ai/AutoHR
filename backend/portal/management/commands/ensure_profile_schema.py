"""Apply users/companies column alters required by the profile wizard (idempotent)."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Ensure PostgreSQL users/companies columns exist for profile wizard (runs database/migrations/001_profile_integrations.sql)."

    def handle(self, *args, **options):
        root = Path(__file__).resolve().parents[4]
        sql_path = root / "database" / "migrations" / "001_profile_integrations.sql"
        if not sql_path.is_file():
            self.stderr.write(self.style.ERROR(f"Missing {sql_path}"))
            return

        statements = []
        for line in sql_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            statements.append(stripped)

        with connection.cursor() as cursor:
            for stmt in statements:
                cursor.execute(stmt)
        self.stdout.write(self.style.SUCCESS(f"Applied {len(statements)} schema statement(s) from 001_profile_integrations.sql"))
