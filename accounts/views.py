from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.http import require_POST
from django.views.generic import CreateView
from django_ratelimit.core import is_ratelimited
from django_ratelimit.exceptions import Ratelimited

from events.models import EventRegistration
from payments.models import PaymentStatus, Transaction
from payments.services import get_outstanding_registrations
from surveys.models import Survey

from .forms import AccountSettingsForm, AddChildForm, ChildLoginForm, CustomUserCreationForm, UsernameRecoveryForm
from .models import Waiver, WaiverSignature
from .utils import (
    dependent_placeholder_email,
    minor_waiver_message,
    send_activation_email,
    send_child_account_created_email,
    send_guardian_request_email,
    send_username_reminder_email,
)

User = get_user_model()

# Dashboard modals other pages may deep-link into with ?open=<name>
DASHBOARD_MODALS = {"settings", "waiver", "household", "events", "billing", "surveys"}


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


def username_recovery_view(request):
    form = UsernameRecoveryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if is_ratelimited(
            request, group="accounts.username_recovery", key="ip", rate="5/h", method="POST", increment=True
        ):
            raise Ratelimited

        user = User.objects.filter(email__iexact=form.cleaned_data["email"], is_active=True).first()
        if user is not None and user.has_real_email:
            send_username_reminder_email(request, user)

        # Same response whether or not the email matched, so this can't be used to probe for accounts
        return redirect("accounts:username_recovery_done")

    return render(request, "accounts/username_recovery_form.html", {"form": form})


def username_recovery_done(request):
    return render(request, "accounts/username_recovery_done.html")


def _build_dashboard_context(user):
    """Shared by the dashboard GET view and the settings-update view."""
    now = timezone.now()

    children = list(user.child_accounts.all())
    child_ids = [child.id for child in children]
    household_ids = [user.id] + child_ids

    # 1. Upcoming Schedule Logic
    household_registrations = list(
        EventRegistration.objects.filter(user_id__in=household_ids, event__end_time__gte=now)
        .select_related("user", "event", "transaction")
        .order_by("event__start_time")
    )
    personal_registrations = [r for r in household_registrations if r.user_id == user.id]
    child_registrations = [r for r in household_registrations if r.user_id in child_ids]

    # 2. Billing & Outstanding Balance Logic (shared with checkout so the totals always match)
    outstanding_registrations = get_outstanding_registrations(household_ids)
    totals = outstanding_registrations.aggregate(total_cents=Sum("final_price_cents"))
    total_balance = (totals["total_cents"] or 0) / 100.0

    # Completed payments (and any refunds on them), newest first, so players can see money going both ways
    payment_history = (
        Transaction.objects.filter(
            registrations__user_id__in=household_ids,
            payment_status__in=[PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED],
            total_amount_cents__gt=0,
        )
        .distinct()
        .order_by("-created_at")
        .prefetch_related(
            Prefetch(
                "registrations",
                queryset=EventRegistration.objects.select_related("user", "event").order_by("event__start_time"),
            )
        )
    )

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

    active_surveys = Survey.objects.open().filter(assignments__user=user).exclude(submissions__user=user).distinct()

    child_survey_entries = []
    for child in children:
        child_surveys = (
            Survey.objects.open().filter(assignments__user=child).exclude(submissions__user=child).distinct()
        )
        child_survey_entries += [{"user": child, "survey": survey} for survey in child_surveys]

    survey_count = len(active_surveys) + len(child_survey_entries)

    return {
        "personal_registrations": personal_registrations,
        "child_registrations": child_registrations,
        "has_children": len(child_ids) > 0,
        "outstanding_registrations": outstanding_registrations,  # Added
        "total_balance": total_balance,  # Added
        "payment_history": payment_history,
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
        "minor_waiver_message": minor_waiver_message(user),
    }


def _child_login_prefix(child):
    # Every child's login form sits on the same page, so each needs its own field ids.
    return f"child-{child.pk}"


def _render_dashboard(request, open_modal=None, settings_form=None, add_child_form=None, child_login_form=None):
    """
    Renders the dashboard with fresh forms, swapping in whichever bound form failed
    validation (and opening its modal) so the errors stay visible.
    """
    user = request.user
    context = _build_dashboard_context(user)
    context["settings_form"] = settings_form or AccountSettingsForm(instance=user)
    context["add_child_form"] = add_child_form or AddChildForm()
    context["child_logins"] = [
        (
            child,
            child_login_form
            if child_login_form is not None and child_login_form.child.pk == child.pk
            else ChildLoginForm(child=child, prefix=_child_login_prefix(child)),
        )
        for child in context["dependents"]
    ]
    context["open_modal"] = open_modal
    return render(request, "accounts/dashboard.html", context)


@login_required
def account_dashboard_view(request):
    open_modal = request.GET.get("open")
    return _render_dashboard(request, open_modal=open_modal if open_modal in DASHBOARD_MODALS else None)


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
    return _render_dashboard(request, open_modal="settings", settings_form=form)


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

    # Minors never sign for themselves; their parent or guardian signs on their behalf.
    if target_user == request.user and (message := minor_waiver_message(target_user)):
        messages.warning(request, message)
        return redirect("accounts:dashboard")

    # get_or_create rather than create: guards against a double-submit
    # (e.g. double-click) tripping the unique_together constraint.
    WaiverSignature.objects.get_or_create(user=target_user, waiver=waiver)

    if target_user == request.user:
        messages.success(request, "Thank you for signing the waiver.")
    else:
        messages.success(request, f"Thank you for signing the waiver on behalf of {target_user}.")
    return redirect("accounts:dashboard")


def _redirect_to_household():
    return redirect(f"{reverse('accounts:dashboard')}?open=household")


@login_required
@require_POST
def add_child_view(request):
    if not request.user.can_manage_dependents:
        raise PermissionDenied("Only adult accounts can add children.")

    form = AddChildForm(request.POST)
    if not form.is_valid():
        return _render_dashboard(request, open_modal="household", add_child_form=form)

    if form.link_target is not None:
        # Re-check under a row lock to close the gap between form validation and this
        # save, in case two parents race to claim the same teen.
        with transaction.atomic():
            teen = User.objects.select_for_update().get(pk=form.link_target.pk)
            if teen.parent_account_id is not None or teen.pending_guardian_id is not None:
                messages.error(request, f"{teen} is no longer available to link.")
                return _redirect_to_household()
            teen.pending_guardian = request.user
            teen.save(update_fields=["pending_guardian"])
        send_guardian_request_email(request, teen, request.user)
        messages.success(
            request,
            f"{teen} already has an account, so we've sent them a request to link to you. "
            "They'll join your household once they approve it from their dashboard.",
        )
        return _redirect_to_household()

    data = form.cleaned_data
    child = User(
        first_name=data["first_name"],
        last_name=data["last_name"],
        date_of_birth=data["date_of_birth"],
        username=data["username"],
        parent_account=request.user,
    )
    child.set_password(data["password1"])
    if data["email"]:
        child.email = data["email"]
        child.is_active = False  # Until they confirm the address, same as a normal signup
    else:
        child.email = dependent_placeholder_email(child.username)
        child.is_active = True

    try:
        child.save()
    except ValidationError:
        # The username or email was taken between validation and save
        form.add_error(None, "That username or email was just taken, please choose another.")
        return _render_dashboard(request, open_modal="household", add_child_form=form)

    send_child_account_created_email(request, child)
    if data["email"]:
        send_activation_email(request, child)
        messages.success(
            request,
            f"{child.get_full_name()} has been added. We emailed {child.email} a confirmation link; "
            f"once it's confirmed they can log in as {child.username}.",
        )
    else:
        messages.success(request, f"{child.get_full_name()} has been added. They can log in now as {child.username}.")
    return _redirect_to_household()


@login_required
@require_POST
def update_child_login_view(request, user_id):
    child = get_object_or_404(request.user.child_accounts.all(), id=user_id)
    form = ChildLoginForm(request.POST, child=child, prefix=_child_login_prefix(child))
    if not form.is_valid():
        return _render_dashboard(request, open_modal="household", child_login_form=form)

    data = form.cleaned_data
    child.username = data["username"]
    if data["password1"]:
        child.set_password(data["password1"])

    email_changed = False
    if data["email"]:
        if data["email"].lower() != child.email.lower():
            child.email = data["email"]
            child.is_active = False  # Until they confirm the new address
            email_changed = True
    else:
        if child.has_real_email:
            child.is_active = True  # Email removed, so there's nothing left to confirm
        child.email = dependent_placeholder_email(child.username)

    try:
        child.save()
    except ValidationError:
        form.add_error(None, "That username or email was just taken, please choose another.")
        return _render_dashboard(request, open_modal="household", child_login_form=form)

    if email_changed:
        send_activation_email(request, child)
        messages.success(
            request,
            f"Updated {child.get_full_name()}'s login. We emailed {child.email} a confirmation link; "
            "they can log in once it's confirmed.",
        )
    else:
        messages.success(request, f"Updated {child.get_full_name()}'s login.")
    return _redirect_to_household()


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
