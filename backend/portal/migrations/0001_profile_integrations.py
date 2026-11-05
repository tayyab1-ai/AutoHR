# Generated for profile wizard & OAuth tables

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ProfileSetup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField(db_index=True, unique=True)),
                ("company_id", models.UUIDField(db_index=True)),
                ("current_step", models.PositiveSmallIntegerField(default=1)),
                ("step_data", models.JSONField(blank=True, default=dict)),
                ("completed_steps", models.JSONField(blank=True, default=list)),
                ("profile_complete", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "profile_setup"},
        ),
        migrations.CreateModel(
            name="IntegrationConnection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField(db_index=True)),
                ("provider", models.CharField(max_length=40)),
                ("status", models.CharField(default="not_connected", max_length=32)),
                ("connected_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("scopes", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "integration_connections",
                "unique_together": {("user_id", "provider")},
            },
        ),
        migrations.CreateModel(
            name="OAuthCredential",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField(db_index=True)),
                ("provider", models.CharField(max_length=40)),
                ("access_token_enc", models.TextField(blank=True, null=True)),
                ("refresh_token_enc", models.TextField(blank=True, null=True)),
                ("token_expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "oauth_credentials",
                "unique_together": {("user_id", "provider")},
            },
        ),
    ]
