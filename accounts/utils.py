from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify


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


def generate_unique_username(first_name, last_name):
    """Auto-generates a username for a dependent profile, which has no email/password
    of its own for a parent to pick one from. Not race-safe by itself — callers that
    create the user should retry on a ValidationError from full_clean()'s uniqueness check."""
    User = get_user_model()
    base = slugify(f"{first_name}-{last_name}") or "player"
    username = base
    suffix = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix += 1
        username = f"{base}{suffix}"
    return username


def dependent_placeholder_email(username):
    """Dependent profiles have no real email, but `email` stays required+unique at the
    model level: AbstractUser.clean() unconditionally runs email through
    normalize_email(), which turns None into "" (`email or ""`) — so a second
    null-email dependent would collide on the unique constraint the moment full_clean()
    runs. `.invalid` is reserved by RFC 2606 for addresses guaranteed not to resolve,
    and this is never used to actually send mail (dependents can't log in or trigger
    any email flow)."""
    return f"{username}@dependent.invalid"
