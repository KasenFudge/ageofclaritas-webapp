from django.db.models.signals import post_save
from django.dispatch import receiver

from events.models import EventRegistration

from .models import Survey, SurveyAssignment, SurveyType
from .services import sync_survey_assignments
from .utils import send_survey_assignment_email


@receiver(post_save, sender=Survey)
def sync_assignments_on_survey_save(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.event_id:
        return
    sync_survey_assignments(instance)


@receiver(post_save, sender=EventRegistration)
def sync_assignments_on_checkin(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.checked_in:
        return
    surveys = Survey.objects.filter(
        event_id=instance.event_id,
        is_active=True,
        survey_type__in=[SurveyType.FEEDBACK, SurveyType.DOWNTIME, SurveyType.NEW_PLAYER],
    )
    for survey in surveys:
        sync_survey_assignments(survey)


@receiver(post_save, sender=SurveyAssignment)
def email_on_manual_assignment(sender, instance, created, raw=False, **kwargs):
    # Covers assignments created one at a time (e.g. the admin inline for OTHER-type
    # surveys) -- bulk_create paths in services.sync_survey_assignments() email directly
    # since bulk_create never fires this signal.
    if raw or not created:
        return
    send_survey_assignment_email(instance.survey, instance.user)
