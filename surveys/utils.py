from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_survey_assignment_email(survey, user):
    site = Site.objects.get_current()
    context = {
        "user": user,
        "survey": survey,
        "domain": site.domain,
        "protocol": "http" if settings.DEBUG else "https",
    }

    subject = f"New survey: {survey.title}"
    text_content = render_to_string("emails/survey_assignment_email.txt", context)
    html_content = render_to_string("emails/survey_assignment_email.html", context)

    email = EmailMultiAlternatives(subject, text_content, to=[user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
