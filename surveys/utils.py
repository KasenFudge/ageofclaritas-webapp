from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from accounts.utils import send_to_household

from .eligibility import is_new_player_for_event
from .models import SurveyType

# Order matters: this is the order surveys are listed in the "All players" sentence.
SURVEY_TYPE_LABELS = {
    SurveyType.FEEDBACK: "Our optional feedback survey",
    SurveyType.DOWNTIME: "Our survey for what you would like your character to do in their downtime",
    SurveyType.LUDUS: "Our Ludus survey if you are a noble",
}


def _survey_url(survey, domain, protocol):
    return f"{protocol}://{domain}{reverse('surveys:respond', args=[survey.pk])}"


def _build_event_recap_email(user, event_surveys, domain, protocol):
    event = event_surveys[0].event

    new_player_survey = next(
        (s for s in event_surveys if s.survey_type == SurveyType.NEW_PLAYER and is_new_player_for_event(user, s.event)),
        None,
    )
    other_surveys = [s for s in event_surveys if s.survey_type in SURVEY_TYPE_LABELS]
    other_surveys.sort(key=lambda s: list(SURVEY_TYPE_LABELS).index(s.survey_type))

    text_new_player = (
        f"our new player survey: {_survey_url(new_player_survey, domain, protocol)}" if new_player_survey else ""
    )
    html_new_player = (
        format_html('<a href="{}">our new player survey</a>', _survey_url(new_player_survey, domain, protocol))
        if new_player_survey
        else ""
    )

    text_other = "\n".join(
        f"- {SURVEY_TYPE_LABELS[s.survey_type]}: {_survey_url(s, domain, protocol)}" for s in other_surveys
    )
    html_other = mark_safe(
        "".join(
            format_html(
                '<li><a href="{}">{}</a></li>', _survey_url(s, domain, protocol), SURVEY_TYPE_LABELS[s.survey_type]
            )
            for s in other_surveys
        )
    )

    subject = f"Thank you for attending {event.title}!"
    text_content = render_to_string(
        "emails/survey_event_recap_email.txt",
        {"user": user, "new_player_line": text_new_player, "other_line": text_other},
    )
    html_content = render_to_string(
        "emails/survey_event_recap_email.html",
        {"user": user, "new_player_line": html_new_player, "other_line": html_other},
    )
    return subject, text_content, html_content


def _build_plain_survey_email(user, survey, domain, protocol):
    context = {
        "user": user,
        "survey": survey,
        "domain": domain,
        "protocol": protocol,
    }
    text_content = render_to_string("emails/survey_assignment_email.txt", context)
    html_content = render_to_string("emails/survey_assignment_email.html", context)
    return f"New survey: {survey.title}", text_content, html_content


def send_survey_assignment_email(user, surveys):
    """
    Sends one email covering every survey in `surveys` that was just assigned to `user` together.
    See `accounts.utils.email_recipients` for who actually receives it -- the user if they have a real email,
    plus their linked parent or guardian whenever they have one.
    """
    site = Site.objects.get_current()
    protocol = "http" if settings.DEBUG else "https"

    event_surveys = [s for s in surveys if s.event_id]
    plain_surveys = [s for s in surveys if not s.event_id]

    if event_surveys:
        subject, text_content, html_content = _build_event_recap_email(user, event_surveys, site.domain, protocol)
        send_to_household(user, subject, text_content, html_content)

    for survey in plain_surveys:
        subject, text_content, html_content = _build_plain_survey_email(user, survey, site.domain, protocol)
        send_to_household(user, subject, text_content, html_content)
