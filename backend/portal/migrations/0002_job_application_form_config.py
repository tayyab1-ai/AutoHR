import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0001_profile_integrations"),
    ]

    operations = [
        migrations.CreateModel(
            name="JobApplicationFormConfig",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("job_id", models.UUIDField(db_index=True, unique=True)),
                ("company_id", models.UUIDField(db_index=True)),
                ("application_form_title", models.CharField(blank=True, max_length=300, null=True)),
                ("form_description", models.TextField(blank=True, null=True)),
                ("selected_fields", models.JSONField(blank=True, default=list)),
                ("allow_multiple_responses", models.BooleanField(default=False)),
                ("google_form_id", models.CharField(blank=True, max_length=120, null=True)),
                ("google_form_url", models.URLField(blank=True, max_length=500, null=True)),
                ("spreadsheet_id", models.CharField(blank=True, max_length=120, null=True)),
                ("spreadsheet_url", models.URLField(blank=True, max_length=500, null=True)),
                ("status", models.CharField(default="draft", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "job_application_form_configs"},
        ),
    ]
