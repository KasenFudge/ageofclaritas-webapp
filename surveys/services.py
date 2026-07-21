from django.contrib.auth import get_user_model

from events.models import EventRegistration

from .models import Survey, SurveyAssignment, SurveyType
from .utils import send_survey_assignment_email


def _attendee_user_ids(event):
    return set(EventRegistration.objects.filter(event=event, checked_in=True).values_list("user_id", flat=True))


def _new_player_user_ids(event):
    candidates = EventRegistration.objects.filter(event=event, checked_in=True, user__is_veteran=False)
    ids = []
    for reg in candidates:
        first = (
            EventRegistration.objects.filter(user_id=reg.user_id, checked_in=True)
            .order_by("event__start_time", "id")
            .first()
        )
        if first and first.event_id == event.id:
            ids.append(reg.user_id)
    return ids


def eligible_user_ids_for_survey(survey):
    if not survey.event_id:
        return []
    if survey.survey_type in (SurveyType.FEEDBACK, SurveyType.DOWNTIME):
        return _attendee_user_ids(survey.event)
    if survey.survey_type == SurveyType.NEW_PLAYER:
        return _new_player_user_ids(survey.event)
    return []  # OTHER is always manual


def sync_survey_assignments(survey: Survey) -> int:
    user_ids = eligible_user_ids_for_survey(survey)
    existing = set(survey.assignments.values_list("user_id", flat=True))
    new_ids = [uid for uid in user_ids if uid not in existing]
    if not new_ids:
        return 0

    # bulk_create doesn't fire post_save, so the SurveyAssignment signal won't send these --
    # email the newly-assigned users directly here instead.
    SurveyAssignment.objects.bulk_create(
        [SurveyAssignment(survey=survey, user_id=uid) for uid in new_ids], ignore_conflicts=True
    )
    for user in get_user_model().objects.filter(id__in=new_ids):
        send_survey_assignment_email(survey, user)

    return len(new_ids)
