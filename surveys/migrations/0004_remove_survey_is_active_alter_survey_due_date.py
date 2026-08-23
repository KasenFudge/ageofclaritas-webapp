from datetime import datetime, time, timedelta

from django.db import migrations, models
from django.utils import timezone


def backfill_due_dates(apps, schema_editor):
    """Defensive backfill before due_date becomes NOT NULL. Survey.save() has always
    populated due_date on write, so this should be a no-op in practice, but historical
    models can't call the real _default_due_date_for_event(), so the logic is reproduced
    here."""
    Survey = apps.get_model("surveys", "Survey")
    for survey in Survey.objects.filter(due_date__isnull=True).select_related("event"):
        if survey.event_id and survey.event.end_time:
            base_date = timezone.localtime(survey.event.end_time).date()
        else:
            base_date = timezone.localdate()
        due = datetime.combine(base_date + timedelta(weeks=2), time(23, 59, 59))
        survey.due_date = timezone.make_aware(due)
        survey.save(update_fields=["due_date"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("surveys", "0003_alter_survey_survey_type_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_due_dates, noop),
        migrations.AlterField(
            model_name="survey",
            name="due_date",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Defaults to two weeks after the linked event ends (or two weeks from today if no "
                    "event is linked), at 11:59:59 PM. Surveys stop accepting responses once this passes."
                ),
            ),
        ),
        migrations.RemoveField(
            model_name="survey",
            name="is_active",
        ),
    ]
