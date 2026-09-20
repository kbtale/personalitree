"""Model instruments (frameworks, traits, items) instead of string labels.

Answers and profiles recorded before instruments existed carry ad-hoc string
framework labels and cannot be mapped onto an instrument that was never loaded,
so they are deleted here.
"""

import django.db.models.deletion
from django.db import migrations, models


def delete_string_labelled_rows(apps, schema_editor):
    """Remove rows recorded before instruments existed."""
    for model_name in ("QuestionnaireResponse", "ProfileResult", "Question"):
        apps.get_model("core", model_name).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_encrypt_burner_password"),
    ]

    operations = [
        migrations.RunPython(
            delete_string_labelled_rows,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="Framework",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                ("citation", models.TextField(blank=True, default="")),
                (
                    "source_url",
                    models.URLField(blank=True, default="", max_length=500),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("slug",),
            },
        ),
        migrations.CreateModel(
            name="Trait",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=100)),
                ("name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "framework",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="traits",
                        to="core.framework",
                    ),
                ),
            ],
            options={
                "ordering": ("slug",),
                "unique_together": {("framework", "slug")},
            },
        ),
        migrations.AlterUniqueTogether(
            name="profileresult",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="profileresult",
            name="framework_name",
        ),
        migrations.AddField(
            model_name="profileresult",
            name="framework",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profile_results",
                to="core.framework",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="profileresult",
            unique_together={("target", "framework")},
        ),
        migrations.AlterUniqueTogether(
            name="question",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="question",
            name="framework_name",
        ),
        migrations.RemoveField(
            model_name="question",
            name="trait",
        ),
        migrations.AddField(
            model_name="question",
            name="framework",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to="core.framework",
            ),
        ),
        migrations.AddField(
            model_name="question",
            name="trait",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="questions",
                to="core.trait",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="question",
            unique_together={("framework", "question_id")},
        ),
    ]
