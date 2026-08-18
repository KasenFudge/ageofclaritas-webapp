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


def _recipients_for(user):
    """
    Who actually receives a survey-assignment email for `user`:
    - 13 and under: their linked parent only (dependent accounts have no real email).
    - 14-17: both the linked parent and the teen themselves, if they have a real usable
      account -- a safeguard for accounts that never "aged up" out of dependent status.
    - 18+ (or age unknown): the user themselves.
    """
    age = user.age
    if age is not None and age <= 13:
        return [user.parent_account] if user.parent_account_id else []
    if age is not None and age <= 17:
        recipients = [user.parent_account] if user.parent_account_id else []
        if user.has_usable_password():
            recipients.append(user)
        return recipients
    return [user]


def _dispatch(user, subject, text_content, html_content):
    for recipient in _recipients_for(user):
        if recipient != user:
            subject = f"For {user.first_name or user.username}: {subject}"
        email = EmailMultiAlternatives(subject, text_content, to=[recipient.email])
        email.attach_alternative(html_content, "text/html")
        email.send()


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
    See `_recipients_for` for who actually receives it -- may be `user`, their parent, or both, depending on age.
    """
    site = Site.objects.get_current()
    protocol = "http" if settings.DEBUG else "https"

    event_surveys = [s for s in surveys if s.event_id]
    plain_surveys = [s for s in surveys if not s.event_id]

    if event_surveys:
        subject, text_content, html_content = _build_event_recap_email(user, event_surveys, site.domain, protocol)
        _dispatch(user, subject, text_content, html_content)

    for survey in plain_surveys:
        subject, text_content, html_content = _build_plain_survey_email(user, survey, site.domain, protocol)
        _dispatch(user, subject, text_content, html_content)
