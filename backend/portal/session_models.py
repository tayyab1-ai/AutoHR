import uuid

from django.db import models


class HrUserSession(models.Model):
    """Tracks each Django session cookie for an HR user (multi-device sign-in)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    session_key = models.CharField(max_length=40, unique=True)
    device_label = models.CharField(max_length=200, blank=True, default="")
    user_agent = models.TextField(blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user_id", "revoked_at"]),
        ]
