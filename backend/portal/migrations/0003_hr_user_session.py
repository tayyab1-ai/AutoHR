# Generated for Google session tracking

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_job_application_form_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="HrUserSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("user_id", models.UUIDField(db_index=True)),
                ("session_key", models.CharField(max_length=40, unique=True)),
                ("device_label", models.CharField(blank=True, default="", max_length=200)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "indexes": [models.Index(fields=["user_id", "revoked_at"], name="portal_hrus_user_id_rev_idx")],
            },
        ),
    ]
