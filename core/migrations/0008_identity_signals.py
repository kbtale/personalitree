"""Give discovered accounts evidence instead of a hardcoded confidence."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_instruments"),
    ]

    operations = [
        migrations.RenameField(
            model_name="discoveredaccount",
            old_name="verification_confidence",
            new_name="confidence",
        ),
        migrations.AddField(
            model_name="discoveredaccount",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="discoveredaccount",
            name="signals",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
