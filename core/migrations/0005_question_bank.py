"""Replace the questionnaire response string id with a question reference.

Responses recorded before the question bank existed cannot be mapped to a
question, so they are deleted before the foreign key is added.
"""

import django.db.models.deletion
from django.db import migrations, models


def delete_pre_bank_responses(apps, schema_editor):
    """Remove responses recorded before the question bank existed."""
    questionnaire_response = apps.get_model("core", "QuestionnaireResponse")
    questionnaire_response.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_target_lifecycle"),
    ]

    operations = [
        migrations.RunPython(
            delete_pre_bank_responses,
            migrations.RunPython.noop,
        ),
        migrations.CreateModel(
            name="Question",
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
                ("question_id", models.CharField(max_length=50)),
                (
                    "framework_name",
                    models.CharField(
                        choices=[("Big Five", "Big Five")],
                        max_length=100,
                    ),
                ),
                ("trait", models.CharField(max_length=50)),
                ("text", models.TextField()),
                ("reverse_scored", models.BooleanField(default=False)),
                ("min_score", models.PositiveSmallIntegerField(default=1)),
                ("max_score", models.PositiveSmallIntegerField(default=5)),
            ],
            options={
                "ordering": ("question_id",),
                "unique_together": {("framework_name", "question_id")},
            },
        ),
        migrations.AlterUniqueTogether(
            name="questionnaireresponse",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="questionnaireresponse",
            name="question_id",
        ),
        migrations.AddField(
            model_name="questionnaireresponse",
            name="question",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="responses",
                to="core.question",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="questionnaireresponse",
            unique_together={("target", "question")},
        ),
        migrations.AlterModelOptions(
            name="questionnaireresponse",
            options={"ordering": ("question__question_id",)},
        ),
        migrations.AlterField(
            model_name="profileresult",
            name="framework_name",
            field=models.CharField(
                choices=[("Big Five", "Big Five")],
                max_length=100,
            ),
        ),
    ]
