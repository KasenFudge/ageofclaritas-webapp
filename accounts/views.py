from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from events.models import EventRegistration
from payments.models import PaymentStatus
from surveys.models import Survey

from .forms import AccountSettingsForm, CustomUserCreationForm
from .models import Waiver, WaiverSignature

User = get_user_model()


class UserRegistrationView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        # 1. Save the user but don't commit to the database yet
        user = form.save(commit=False)

        # 2. Set user as inactive so they cannot log in
        user.is_active = False
        user.save()

        # 3. Generate the secure token and user ID
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        # 4. Build the activation URL
        current_site = get_current_site(self.request)
        domain = current_site.domain

        # 5. Prepare the email content
        context = {
            "user": user,
            "domain": domain,
            "uid": uid,
            "token": token,
            "protocol": "https" if self.request.is_secure() else "http",
        }

        subject = "Verify your account"
        text_content = render_to_string("emails/activation_email.txt", context)
        html_content = render_to_string("emails/activation_email.html", context)

        # 6. Send the email using your newly configured Resend API
        email = EmailMultiAlternatives(subject, text_content, to=[user.email])
        email.attach_alternative(html_content, "text/html")
        email.send()

        messages.success(self.request, "Registration successful! Please check your email to verify your account.")
        return redirect(self.success_url)


def activate_account(request, uidb64, token):
    try:
        # Decode the user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Verify the token
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Your account has been successfully verified! You can now log in.")
        return redirect("accounts:login")
    else:
        messages.error(request, "The activation link is invalid or has expired. Please register again.")
        return redirect("accounts:register")


def _build_dashboard_context(user):
    """Shared by the dashboard GET view and the settings-update view."""
    now = timezone.now()

    child_ids = list(user.child_accounts.values_list("id", flat=True))
    household_ids = [user.id] + child_ids

    # 1. Upcoming Schedule Logic
    household_registrations = list(
        EventRegistration.objects.filter(event__end_time__gte=now)
        .select_related("user", "event", "transaction")
        .order_by("event__start_time")
    )
    personal_registrations = [r for r in household_registrations if r.user_id == user.id]
    child_registrations = [r for r in household_registrations if r.user_id in child_ids]

    # 2. Billing & Outstanding Balance Logic
    outstanding_registrations = (
        EventRegistration.objects.filter(user_id__in=household_ids)
        .filter(
            Q(transaction__isnull=True)
            | Q(transaction__payment_status=PaymentStatus.INCOMPLETE)
            | Q(transaction__payment_status=PaymentStatus.FAILED)
        )
        .filter(Q(event__end_time__gte=now) | Q(checked_in=True))
        .select_related("user", "event")
        .order_by("event__start_time")
    )
    totals = outstanding_registrations.aggregate(total_cents=Sum("final_price_cents"))
    total_balance = (totals["total_cents"] or 0) / 100.0

    # 3. Waivers & Surveys Logic
    active_waiver = Waiver.objects.filter(is_active=True).first()
    has_signed_current_waiver = user.has_signed_active_waiver()

    current_signature = None
    if active_waiver and has_signed_current_waiver:
        current_signature = user.waiver_signatures.filter(waiver=active_waiver).first()

    past_waivers = user.waiver_signatures.select_related("waiver").order_by("-signed_at")
    if active_waiver and has_signed_current_waiver:
        past_waivers = past_waivers.exclude(waiver=active_waiver)

    active_surveys = Survey.objects.filter(is_active=True).exclude(submissions__user=user).distinct()

    return {
        "personal_registrations": personal_registrations,
        "child_registrations": child_registrations,
        "has_children": len(child_ids) > 0,
        "outstanding_registrations": outstanding_registrations,  # Added
        "total_balance": total_balance,  # Added
        "active_waiver": active_waiver,
        "has_signed_current_waiver": has_signed_current_waiver,
        "current_signature": current_signature,
        "past_waivers": past_waivers,
        "active_surveys": active_surveys,
    }


@login_required
def account_dashboard_view(request):
    user = request.user
    context = _build_dashboard_context(user)
    context["settings_form"] = AccountSettingsForm(instance=user)
    return render(request, "accounts/dashboard.html", context)


@login_required
@require_POST
def update_account_settings_view(request):
    form = AccountSettingsForm(request.POST, instance=request.user)

    if form.is_valid():
        form.save()
        messages.success(request, "Your account settings have been updated.")
        return redirect("accounts:dashboard")

    # Invalid submission: re-render the full dashboard directly (rather than
    # redirect) so the bound form + its errors survive, and force the
    # Settings modal open so the errors are actually visible.
    context = _build_dashboard_context(request.user)
    context["settings_form"] = form
    context["open_modal"] = "settings"
    return render(request, "accounts/dashboard.html", context)


@login_required
@require_POST
def sign_waiver_view(request):
    waiver = get_object_or_404(Waiver, pk=request.POST.get("waiver_id"), is_active=True)
    # get_or_create rather than create: guards against a double-submit
    # (e.g. double-click) tripping the unique_together constraint.
    WaiverSignature.objects.get_or_create(user=request.user, waiver=waiver)
    messages.success(request, "Thank you for signing the waiver.")
    return redirect("accounts:dashboard")
