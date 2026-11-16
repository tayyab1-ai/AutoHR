"""In-process background worker that periodically syncs Google Form responses.

Started from ``PortalConfig.ready()`` when the web server runs, so new applications
arrive without HR pressing "Sync". Interval comes from ``FORM_SYNC_INTERVAL_SECONDS``
(default 300s; set to 0 to disable). For production with several server processes,
disable this and run ``python manage.py sync_google_form_responses --interval 300``
as a single dedicated worker instead.
"""

from __future__ import annotations

import logging
import os
import sys
import threading

_logger = logging.getLogger(__name__)
_started = False
_lock = threading.Lock()


def _interval_seconds() -> int:
    try:
        return max(0, int(os.environ.get("FORM_SYNC_INTERVAL_SECONDS", "300")))
    except ValueError:
        return 300


def _should_start() -> bool:
    if os.environ.get("AUTOHR_FORM_SYNC_WORKER") == "1":
        return True
    argv = sys.argv
    if len(argv) < 2 or argv[1] != "runserver":
        return False  # management commands, tests, scripts
    # Under the autoreloader only the child process (RUN_MAIN=true) serves requests.
    return os.environ.get("RUN_MAIN") == "true" or "--noreload" in argv


def _loop(interval: int, stop: threading.Event) -> None:
    from django.db import close_old_connections

    from .google_form_sync_service import sync_all_active_forms

    # Give the server a moment to finish booting.
    if stop.wait(15):
        return
    while not stop.is_set():
        try:
            summary = sync_all_active_forms()
            if summary.get("total_synced"):
                _logger.info("Auto form sync: %s new application(s).", summary["total_synced"])
        except Exception:
            _logger.exception("Auto form sync cycle failed")
        finally:
            close_old_connections()
        stop.wait(interval)


def start_background_form_sync() -> None:
    global _started
    interval = _interval_seconds()
    if interval <= 0 or not _should_start():
        return
    with _lock:
        if _started:
            return
        _started = True
    stop = threading.Event()
    t = threading.Thread(target=_loop, args=(interval, stop), name="autohr-form-sync", daemon=True)
    t.start()
    _logger.info("Google Form auto-sync worker started (every %ss).", interval)
