"""Apply users/companies column alters from database/migrations/*.sql (idempotent)."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Ensure PostgreSQL schema patches under database/migrations/ are applied (idempotent)."

    def handle(self, *args, **options):
        root = Path(__file__).resolve().parents[4]
        mig_dir = root / "database" / "migrations"
        if not mig_dir.is_dir():
            self.stderr.write(self.style.ERROR(f"Missing {mig_dir}"))
            return

        sql_files = sorted(mig_dir.glob("*.sql"))
        total = 0
        with connection.cursor() as cursor:
            for sql_path in sql_files:
                statements = []
                for line in sql_path.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("--"):
                        continue
                    statements.append(stripped)
                for stmt in statements:
                    cursor.execute(stmt)
                    total += 1
                self.stdout.write(self.style.SUCCESS(f"Applied {len(statements)} statement(s) from {sql_path.name}"))

        self.stdout.write(self.style.SUCCESS(f"Done — {total} SQL statement(s) total."))
