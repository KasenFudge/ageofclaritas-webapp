from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView
from django_ratelimit.core import is_ratelimited
from django_ratelimit.exceptions import Ratelimited

from events.models import EventRegistration
from payments.models import PaymentStatus
from surveys.models import Survey

from .forms import AccountSettingsForm, AddDependentForm, CustomUserCreationForm, GuardianLinkRequestForm
from .models import Waiver, WaiverSignature
from .utils import dependent_placeholder_email, generate_unique_username, send_activation_email

User = get_user_model()


class UserRegistrationView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        # Only count actual account creations against the limit, not invalid
        # submissions (weak/mismatched passwords, the under-14 age gate, etc.) —
        # a decorator on the whole post() method would burn quota on typos alone.
        if is_ratelimited(self.request, group="accounts.register", key="ip", rate="5/h", method="POST", increment=True):
            raise Ratelimited

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

    active_surveys = (
        Survey.objects.filter(is_active=True, assignments__user=user).exclude(submissions__user=user).distinct()
    )

    child_survey_entries = []
    for child in children:
        child_surveys = (
            Survey.objects.filter(is_active=True, assignments__user=child).exclude(submissions__user=child).distinct()
        )
        child_survey_entries += [{"user": child, "survey": survey} for survey in child_surveys]

    survey_count = len(active_surveys) + len(child_survey_entries)

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
        "child_survey_entries": child_survey_entries,
        "survey_count": survey_count,
        "dependents": children,
        "can_manage_dependents": user.can_manage_dependents,
        "pending_guardian_requests_sent": list(user.pending_dependents.all()) if user.can_manage_dependents else [],
        "incoming_guardian_request": user.pending_guardian,
    }


@login_required
def account_dashboard_view(request):
    user = request.user
    context = _build_dashboard_context(user)
    context["settings_form"] = AccountSettingsForm(instance=user)
    context["dependent_form"] = AddDependentForm()
    context["guardian_link_form"] = GuardianLinkRequestForm()
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

    if target_user.needs_guardian_link:
        messages.warning(request, f"{target_user} needs a confirmed guardian linked before signing a waiver.")
        return redirect("accounts:dashboard")

    # get_or_create rather than create: guards against a double-submit
    # (e.g. double-click) tripping the unique_together constraint.
    WaiverSignature.objects.get_or_create(user=target_user, waiver=waiver)

    if target_user == request.user:
        messages.success(request, "Thank you for signing the waiver.")
    else:
        messages.success(request, f"Thank you for signing the waiver on behalf of {target_user}.")
    return redirect("accounts:dashboard")


@login_required
@require_POST
def add_dependent_view(request):
    if not request.user.can_manage_dependents:
        raise PermissionDenied("Only unlinked adult accounts can add dependents.")

    form = AddDependentForm(request.POST)
    if form.is_valid():
        dependent = None
        for _ in range(3):  # retry on a same-instant username collision from another parent
            candidate = form.save(commit=False)
            candidate.username = generate_unique_username(candidate.first_name, candidate.last_name)
            candidate.email = dependent_placeholder_email(candidate.username)
            candidate.set_unusable_password()
            # Must never look like a pending-verification signup to delete_unverified_accounts.
            candidate.is_active = True
            candidate.parent_account = request.user
            try:
                candidate.save()
                dependent = candidate
                break
            except ValidationError:
                continue

        if dependent is None:
            messages.error(request, "Could not create the dependent profile, please try again.")
            return redirect("accounts:dashboard")

        messages.success(request, f"{dependent.get_full_name()} has been added to your household.")
        return redirect("accounts:dashboard")

    context = _build_dashboard_context(request.user)
    context["settings_form"] = AccountSettingsForm(instance=request.user)
    context["dependent_form"] = form
    context["guardian_link_form"] = GuardianLinkRequestForm()
    context["open_modal"] = "household"
    return render(request, "accounts/dashboard.html", context)


@login_required
@require_POST
def request_guardian_link_view(request):
    if not request.user.can_manage_dependents:
        raise PermissionDenied("Only unlinked adult accounts can request a guardian link.")

    form = GuardianLinkRequestForm(request.POST, requesting_user=request.user)
    if form.is_valid():
        target = form.target_user
        # Re-check under a row lock to close the gap between form validation and this
        # save, in case two parents race to claim the same teen.
        with transaction.atomic():
            target = User.objects.select_for_update().get(pk=target.pk)
            if target.parent_account_id is not None or target.pending_guardian_id is not None:
                messages.error(request, f"{target} is no longer available to request.")
                return redirect("accounts:dashboard")
            target.pending_guardian = request.user
            target.save(update_fields=["pending_guardian"])
        messages.success(request, f"Guardian request sent to {target}. They must approve it before the link is active.")
        return redirect("accounts:dashboard")

    context = _build_dashboard_context(request.user)
    context["settings_form"] = AccountSettingsForm(instance=request.user)
    context["dependent_form"] = AddDependentForm()
    context["guardian_link_form"] = form
    context["open_modal"] = "household"
    return render(request, "accounts/dashboard.html", context)


@login_required
@require_POST
def respond_guardian_link_view(request):
    user = request.user
    if not user.pending_guardian_id:
        messages.error(request, "There is no pending guardian request to respond to.")
        return redirect("accounts:dashboard")

    requester = user.pending_guardian
    action = request.POST.get("action")
    if action == "approve":
        user.parent_account = requester
        user.pending_guardian = None
        user.save()
        messages.success(request, f"You are now linked to {requester} as your guardian.")
    elif action == "deny":
        user.pending_guardian = None
        user.save(update_fields=["pending_guardian"])
        messages.info(request, "Guardian request denied.")
    else:
        messages.error(request, "Invalid action.")
    return redirect("accounts:dashboard")
