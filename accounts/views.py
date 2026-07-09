from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from events.models import EventRegistration
from payments.models import PaymentStatus
from surveys.models import Survey

from .forms import AccountSettingsForm, CustomUserCreationForm
from .models import Waiver, WaiverSignature


class UserRegistrationView(CreateView):
    form_class = CustomUserCreationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("login")


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
