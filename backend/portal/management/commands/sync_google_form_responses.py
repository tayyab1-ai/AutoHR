"""Django management command to periodically sync Google Form candidate responses."""

import sys
import time
import uuid

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from portal.google_form_sync_service import sync_all_active_forms, sync_job_form_responses
from portal.models import JobPosting


class Command(BaseCommand):
    help = "Sync candidate submissions from Google Forms into AutoHR candidate & CV scoring pipeline."

    def add_arguments(self, parser):
        parser.add_argument(
            "--job-id",
            type=str,
            default="",
            help="Optional UUID of a specific job posting to sync.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=0,
            help="Interval in seconds for continuous polling worker loop (0 = run once).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-scoring of already synced responses.",
        )

    def handle(self, *args, **options):
        job_id_raw = (options.get("job_id") or "").strip()
        interval = max(0, int(options.get("interval") or 0))
        force = bool(options.get("force"))

        specific_job = None
        if job_id_raw:
            try:
                job_uuid = uuid.UUID(job_id_raw)
                specific_job = JobPosting.objects.filter(id=job_uuid).first()
                if not specific_job:
                    self.stderr.write(self.style.ERROR(f"Job with ID {job_id_raw} does not exist."))
                    return
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid UUID: {job_id_raw}"))
                return

        def _run_sync_cycle():
            now_str = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            self.stdout.write(f"[{now_str}] Running Google Form responses sync cycle...")
            if specific_job:
                res = sync_job_form_responses(specific_job, force_rescore=force)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Job '{specific_job.title}': {res.get('synced_count', 0)} new application(s) synced "
                        f"({res.get('total_responses', 0)} total in form, {res.get('skipped_count', 0)} already processed)."
                    )
                )
                if res.get("errors"):
                    for err in res["errors"]:
                        self.stderr.write(self.style.WARNING(f"  - {err}"))
            else:
                summary = sync_all_active_forms()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"All active jobs: Checked {summary.get('jobs_checked', 0)} job(s), "
                        f"synced {summary.get('total_synced', 0)} new candidate application(s)."
                    )
                )
                for r in summary.get("results", []):
                    if r.get("synced_count", 0) > 0 or r.get("errors"):
                        self.stdout.write(f"  * {r.get('job_title')}: {r.get('synced_count', 0)} synced.")
                        for err in r.get("errors", []):
                            self.stderr.write(self.style.WARNING(f"    - {err}"))

        if interval <= 0:
            _run_sync_cycle()
            return

        self.stdout.write(self.style.NOTICE(f"Starting Google Forms automated sync worker (interval: {interval}s)..."))
        self.stdout.write("Press Ctrl+C to stop.")
        try:
            while True:
                try:
                    _run_sync_cycle()
                except Exception as exc:  # keep the worker alive
                    self.stderr.write(self.style.ERROR(f"Sync cycle failed: {exc}"))
                finally:
                    close_old_connections()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nSync worker stopped cleanly."))
            sys.exit(0)

