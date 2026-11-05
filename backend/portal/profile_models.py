import uuid

from django.db import models


class ProfileSetup(models.Model):
    """Per-user wizard progress (Django-managed table)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(unique=True, db_index=True)
    company_id = models.UUIDField(db_index=True)
    current_step = models.PositiveSmallIntegerField(default=1)
    step_data = models.JSONField(default=dict, blank=True)
    completed_steps = models.JSONField(default=list, blank=True)
    profile_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profile_setup"


class IntegrationConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    provider = models.CharField(max_length=40)  # gmail, google_workspace, google_calendar
    status = models.CharField(max_length=32, default="not_connected")
    connected_email = models.EmailField(blank=True, null=True)
    scopes = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_connections"
        unique_together = [["user_id", "provider"]]


class OAuthCredential(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    provider = models.CharField(max_length=40)
    access_token_enc = models.TextField(blank=True, null=True)
    refresh_token_enc = models.TextField(blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "oauth_credentials"
        unique_together = [["user_id", "provider"]]
