from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import DEPENDENT_EMAIL_DOMAIN


def _site_context(request):
    current_site = get_current_site(request)
    return {
        "domain": current_site.domain,
        "protocol": "https" if request.is_secure() else "http",
    }


def _send(subject, template_name, context, to):
    """Renders emails/<template_name>.txt and .html and sends them to the `to` addresses."""
    text_content = render_to_string(f"emails/{template_name}.txt", context)
    html_content = render_to_string(f"emails/{template_name}.html", context)

    email = EmailMultiAlternatives(subject, text_content, to=to)
    email.attach_alternative(html_content, "text/html")
    email.send()


def send_activation_email(request, user):
    context = {
        **_site_context(request),
        "user": user,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }
    _send("Verify your account", "activation_email", context, [user.email])


def email_recipients(user):
    """
    Who receives a notification email about `user`: their linked parent or guardian
    (always, when there is one) plus the user themselves when they have a real email.
    Children added without an email only ever reach the parent.
    """
    recipients = [user.parent_account] if user.parent_account_id else []
    if user.has_real_email and user not in recipients:
        recipients.append(user)
    return recipients


def send_to_household(user, subject, text_content, html_content):
    """Sends a notification about `user` to everyone in email_recipients(user). The parent's
    copy gets the child's name in the subject so it's clear who it's for."""
    for recipient in email_recipients(user):
        recipient_subject = subject
        if recipient != user:
            recipient_subject = f"For {user.first_name or user.username}: {subject}"
        email = EmailMultiAlternatives(recipient_subject, text_content, to=[recipient.email])
        email.attach_alternative(html_content, "text/html")
        email.send()


def send_guardian_request_email(request, teen, adult):
    """Tells a self-registered teen that an adult asked to link as their guardian."""
    context = {**_site_context(request), "teen": teen, "adult": adult}
    _send(f"{adult} wants to link as your guardian", "guardian_request_email", context, [teen.email])


def send_child_account_created_email(request, child):
    """Confirms a new child account (and its username) to the parent who created it."""
    context = {**_site_context(request), "child": child, "parent": child.parent_account}
    _send(
        f"Account created for {child.get_full_name() or child.username}",
        "child_account_created_email",
        context,
        [child.parent_account.email],
    )


def send_username_reminder_email(request, user):
    """Emails `user` their username, plus their children's, since a child without an email of
    their own has no other way to recover it. Goes only to the address on file."""
    context = {**_site_context(request), "user": user, "children": list(user.child_accounts.all())}
    _send("Your Age of Claritas username", "username_reminder_email", context, [user.email])


def minor_waiver_message(user):
    """What to tell a minor who needs a waiver signed, since they can't sign it themselves.
    Returns None for adults."""
    if user.age is None or user.age >= 18:
        return None
    if user.parent_account_id:
        return f"{user.parent_account} needs to sign the liability waiver for you from their dashboard."
    if user.pending_guardian_id:
        return (
            f"Approve {user.pending_guardian}'s guardian request under Household, "
            "then they can sign the liability waiver for you."
        )
    return (
        "A parent or guardian needs to sign the liability waiver for you. Ask them to add you from "
        f"their account's dashboard (Household → Add a child) using your email, {user.email}."
    )


def dependent_placeholder_email(username):
    """Children added without an email have no real address, but `email` stays required+unique
    at the model level: AbstractUser.clean() unconditionally runs email through
    normalize_email(), which turns None into "" (`email or ""`) — so a second
    null-email child would collide on the unique constraint the moment full_clean()
    runs. `.invalid` is reserved by RFC 2606 for addresses guaranteed not to resolve,
    and email_recipients() never sends to it."""
    return f"{username}@{DEPENDENT_EMAIL_DOMAIN}"
