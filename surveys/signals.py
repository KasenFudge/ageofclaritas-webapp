from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from events.models import Event, EventRegistration, EventType

from .models import Survey, SurveyAssignment, SurveyType, _default_due_date_for_event
from .services import clone_template_surveys_for_event, sync_surveys_and_notify
from .utils import send_survey_assignment_email


@receiver(post_save, sender=Event)
def create_surveys_from_templates(sender, instance, created, raw=False, **kwargs):
    if raw or not created or instance.event_type not in (EventType.SENIOR, EventType.JUNIOR):
        return
    clone_template_surveys_for_event(instance)


@receiver(pre_save, sender=Event)
def capture_old_event(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._old_event = None
        return
    try:
        instance._old_event = Event.objects.get(pk=instance.pk)
    except Event.DoesNotExist:
        instance._old_event = None


@receiver(post_save, sender=Event)
def sync_linked_survey_defaults(sender, instance, created, raw=False, **kwargs):
    """A renamed/rescheduled event should keep any still-auto-generated linked survey
    titles/due-dates in sync -- but never touch a survey staff has customized."""
    if raw or created:
        return
    old_event = getattr(instance, "_old_event", None)
    if not old_event:
        return

    old_str, new_str = str(old_event), str(instance)
    title_changed = old_str != new_str
    end_time_changed = old_event.end_time != instance.end_time
    if not title_changed and not end_time_changed:
        return

    for survey in instance.surveys.all():
        update_fields = []

        if title_changed:
            old_auto_title = f"{survey.get_survey_type_display()} Survey for {old_str}"
            if survey.title == old_auto_title:
                survey.title = f"{survey.get_survey_type_display()} Survey for {new_str}"
                update_fields.append("title")

        if end_time_changed and survey.due_date == _default_due_date_for_event(old_event):
            survey.due_date = _default_due_date_for_event(instance)
            update_fields.append("due_date")

        if update_fields:
            survey.save(update_fields=update_fields)


@receiver(post_save, sender=EventRegistration)
def sync_assignments_on_checkin(sender, instance, created, raw=False, **kwargs):
    if raw or not instance.checked_in:
        return
    surveys = Survey.objects.filter(
        event_id=instance.event_id,
        is_active=True,
        survey_type__in=[SurveyType.FEEDBACK, SurveyType.DOWNTIME, SurveyType.NEW_PLAYER],
    )
    # Batched (not a per-survey loop) so on check in the ueer gets all
    # applicable surveys in one email assuming theyu are already created.
    sync_surveys_and_notify(list(surveys))


@receiver(post_save, sender=SurveyAssignment)
def email_on_manual_assignment(sender, instance, created, raw=False, **kwargs):
    """This handles survey assingments created one at a time (i.e. through the SurveyRegistration inline)"""
    if raw or not created:
        return
    send_survey_assignment_email(instance.user, [instance.survey])
