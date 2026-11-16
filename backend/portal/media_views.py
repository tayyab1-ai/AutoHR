"""Access-controlled serving of private uploads (CVs and interview recordings).

Files live under MEDIA_ROOT but are never served publicly: only a signed-in HR user
of the company that owns the job can download them. Works with DEBUG on or off.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404

from .decorators import hr_login_required
from .models import InterviewStage, JobPosting


def _safe_file(*parts: str) -> Path:
    root = Path(settings.MEDIA_ROOT).resolve()
    target = root.joinpath(*parts).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404("File not found.")
    return target


def _file_response(path: Path) -> FileResponse:
    content_type, _ = mimetypes.guess_type(path.name)
    response = FileResponse(path.open("rb"), content_type=content_type or "application/octet-stream")
    response["Content-Disposition"] = f'inline; filename="{path.name}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@hr_login_required
def resume_file_view(request, job_id, filename: str):
    company = request.user.db_user.company
    if not JobPosting.objects.filter(id=job_id, company=company).exists():
        raise Http404("File not found.")
    return _file_response(_safe_file("resumes", str(job_id), filename))


@hr_login_required
def interview_audio_view(request, stage_id, filename: str):
    company = request.user.db_user.company
    if not InterviewStage.objects.filter(
        id=stage_id,
        interview__application__job_posting__company=company,
    ).exists():
        raise Http404("File not found.")
    return _file_response(_safe_file("interviews", str(stage_id), filename))
