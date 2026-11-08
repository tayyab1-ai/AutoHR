from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_hr_user_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobapplicationformconfig",
            name="resume_drive_folder_url",
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
    ]
