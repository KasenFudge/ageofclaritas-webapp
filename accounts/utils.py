from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def send_activation_email(request, user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    current_site = get_current_site(request)

    context = {
        "user": user,
        "domain": current_site.domain,
        "uid": uid,
        "token": token,
        "protocol": "https" if request.is_secure() else "http",
    }

    subject = "Verify your account"
    text_content = render_to_string("emails/activation_email.txt", context)
    html_content = render_to_string("emails/activation_email.html", context)

    email = EmailMultiAlternatives(subject, text_content, to=[user.email])
    email.attach_alternative(html_content, "text/html")
    email.send()
