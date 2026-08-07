from django.db.models.signals import post_save
from django.dispatch import receiver

from events.models import EventRegistration

from .models import Survey, SurveyAssignment, SurveyType
from .services import sync_surveys_and_notify
from .utils import send_survey_assignment_email


@receiver(post_save, sender=EventRegistration)
def sync_assignments_on_checkin(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.checked_in:
        return
    surveys = Survey.objects.filter(
        event_id=instance.event_id,
        is_active=True,
        survey_type__in=[SurveyType.FEEDBACK, SurveyType.DOWNTIME, SurveyType.NEW_PLAYER],
    )
    # Batched (not a per-survey loop) so a first-time player who unlocks both a Feedback
    # and a New Player survey from this one check-in gets a single combined email.
    sync_surveys_and_notify(list(surveys))


@receiver(post_save, sender=SurveyAssignment)
def email_on_manual_assignment(sender, instance, created, raw=False, **kwargs):
    # Covers assignments created one at a time (e.g. the admin inline for OTHER-type
    # surveys) -- bulk_create paths in services.sync_surveys_and_notify() email directly
    # since bulk_create never fires this signal.
    if raw or not created:
        return
    send_survey_assignment_email(instance.user, [instance.survey])
