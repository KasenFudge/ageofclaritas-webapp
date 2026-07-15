from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView
from django_ratelimit.decorators import ratelimit

from events.models import EventRegistration
from payments.models import PaymentStatus
from surveys.models import Survey

from .forms import AccountSettingsForm, CustomUserCreationForm
from .models import Waiver, WaiverSignature
from .utils import send_activation_email

User = get_user_model()


@method_decorator(ratelimit(key="ip", rate="3/h", method="POST", block=True), name="post")
class UserRegistrationView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        # Save the user but don't commit to the database yet
        user = form.save(commit=False)

        # Set user as inactive so they cannot log in
        user.is_active = False
        user.save()

        # Save the email to the session so the next page can read it
        self.request.session["registration_email"] = user.email

        send_activation_email(self.request, user)

        return redirect("accounts:registration_success")


def registration_success(request):
    # Get the email from session, default to empty string if it's missing
    email = request.session.get("registration_email", "")

    return render(request, "accounts/registration_success.html", {"user_email": email})


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


def resend_verification_email(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                messages.info(request, "This account is already verified. Please log in.")
                return redirect("accounts:login")

            # Use the same email logic we created earlier
            send_activation_email(request, user)
            messages.success(request, "Verification email resent! Please check your inbox.")
        except User.DoesNotExist:
            messages.error(request, "No account found with that email address.")

        return redirect("accounts:registration_success")
    return redirect("accounts:register")

    return redirect("accounts:register")


def ratelimited_error(request, exception):
    return render(request, "accounts/ratelimited.html", status=429)


def _build_dashboard_context(user):
    """Shared by the dashboard GET view and the settings-update view."""
    now = timezone.now()

    children = list(user.child_accounts.all())
    child_ids = [child.id for child in children]
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

    # Household waiver status: lets a parent see (and act on) which of their
    # children still need the active waiver signed, right alongside their own.
    child_waiver_status = []
    if active_waiver and children:
        signed_child_ids = set(
            WaiverSignature.objects.filter(waiver=active_waiver, user_id__in=child_ids).values_list(
                "user_id", flat=True
            )
        )
        child_waiver_status = [{"user": child, "has_signed": child.id in signed_child_ids} for child in children]

    household_waiver_pending = bool(active_waiver) and (
        not has_signed_current_waiver or any(not status["has_signed"] for status in child_waiver_status)
    )

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
        "child_waiver_status": child_waiver_status,
        "household_waiver_pending": household_waiver_pending,
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

    # Finds the user's account and any of their child accounts.
    user_id = request.POST.get("user_id")
    if user_id and str(user_id) != str(request.user.id):
        target_user = get_object_or_404(request.user.child_accounts.all(), id=user_id)
    else:
        target_user = request.user

    # get_or_create rather than create: guards against a double-submit
    # (e.g. double-click) tripping the unique_together constraint.
    WaiverSignature.objects.get_or_create(user=target_user, waiver=waiver)

    if target_user == request.user:
        messages.success(request, "Thank you for signing the waiver.")
    else:
        messages.success(request, f"Thank you for signing the waiver on behalf of {target_user}.")
    return redirect("accounts:dashboard")
