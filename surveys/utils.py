from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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


def _send(user, subject, text_content, html_content):
    email = EmailMultiAlternatives(subject, text_content, to=[user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()


def _send_event_recap_email(user, event_surveys, domain, protocol):
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
    _send(user, subject, text_content, html_content)


def send_survey_assignment_email(user, surveys):
    """
    Sends one email covering every survey in `surveys` that was just assigned to `user`
    together. Surveys linked to an event get the warm "thanks for attending" recap
    template, describing each survey type in its own line rather than a generic link;
    surveys with no event (manually-assigned OTHER surveys with nothing to recap) fall
    back to a plain one-line notice, one per survey.
    """
    site = Site.objects.get_current()
    protocol = "http" if settings.DEBUG else "https"

    event_surveys = [s for s in surveys if s.event_id]
    plain_surveys = [s for s in surveys if not s.event_id]

    if event_surveys:
        _send_event_recap_email(user, event_surveys, site.domain, protocol)

    for survey in plain_surveys:
        context = {
            "user": user,
            "survey": survey,
            "domain": site.domain,
            "protocol": protocol,
        }
        text_content = render_to_string("emails/survey_assignment_email.txt", context)
        html_content = render_to_string("emails/survey_assignment_email.html", context)
        _send(user, f"New survey: {survey.title}", text_content, html_content)
