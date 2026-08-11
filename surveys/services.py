from collections import defaultdict

from django.contrib.auth import get_user_model

from .eligibility import attendee_user_ids, new_player_user_ids
from .models import Survey, SurveyAssignment, SurveyQuestion, SurveyType
from .utils import send_survey_assignment_email


def eligible_user_ids_for_survey(survey):
    if not survey.event_id:
        return []
    if survey.survey_type in (SurveyType.FEEDBACK, SurveyType.DOWNTIME):
        return attendee_user_ids(survey.event)
    if survey.survey_type == SurveyType.NEW_PLAYER:
        return new_player_user_ids(survey.event)
    return []  # LUDUS and OTHER are always manual (no auto-eligibility rule yet)


def _create_new_assignments(survey):
    """Create SurveyAssignment rows for survey's newly-eligible users. Returns their ids."""
    user_ids = eligible_user_ids_for_survey(survey)
    existing = set(survey.assignments.values_list("user_id", flat=True))
    new_ids = [uid for uid in user_ids if uid not in existing]
    if new_ids:
        SurveyAssignment.objects.bulk_create(
            [SurveyAssignment(survey=survey, user_id=uid) for uid in new_ids], ignore_conflicts=True
        )
    return new_ids


def sync_surveys_and_notify(surveys) -> int:
    """
    Sync assignments for one or more surveys, batching each user's newly-assigned surveys
    into a single combined email rather than one email per survey -- e.g. a first-time
    player checking in gets one email covering both their Feedback and New Player surveys,
    not two separate ones.
    """
    surveys_by_user = defaultdict(list)
    total_new = 0

    for survey in surveys:
        for user_id in _create_new_assignments(survey):
            surveys_by_user[user_id].append(survey)
            total_new += 1

    if surveys_by_user:
        users = get_user_model().objects.in_bulk(surveys_by_user.keys())
        for user_id, assigned_surveys in surveys_by_user.items():
            send_survey_assignment_email(users[user_id], assigned_surveys)

    return total_new


def clone_template_surveys_for_event(event):
    """
    For newly created events, clone feedback and downtime surveys from a template survey.
    (The template survey is a Survey of the type linked that is not linked to an Event).
    """
    created_surveys = []
    for survey_type in (SurveyType.FEEDBACK, SurveyType.DOWNTIME):
        template = Survey.objects.filter(event__isnull=True, survey_type=survey_type, is_active=True).first()
        if not template:
            continue
        new_survey = Survey.objects.create(event=event, survey_type=survey_type, description=template.description)
        SurveyQuestion.objects.bulk_create(
            [
                # Don't save a title or due date, done automatically on the save for the survey based on the event.
                SurveyQuestion(
                    survey=new_survey, question=sq.question, position=sq.position, is_required=sq.is_required
                )
                for sq in template.survey_questions.all()  # already ordered by position (Meta.ordering)
            ]
        )
        created_surveys.append(new_survey)
    return created_surveys
