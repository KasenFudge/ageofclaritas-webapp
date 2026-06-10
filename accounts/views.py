from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from events.models import EventRegistration
from payments.models import PaymentStatus


@login_required
def upcoming_events_view(request):
    user = request.user
    now = timezone.now()

    # 1. Pull the raw list of child IDs
    child_ids = list(user.child_accounts.values_list("id", flat=True))

    # 2. Query for all future event registrations in the household
    household_pool = (
        EventRegistration.objects.filter(event__start_time__gte=now)
        .select_related("user", "event", "order")
        .order_by("event__start_time")
    )

    # 3. Separate into distinct lists for clean template iteration
    personal_registrations = household_pool.filter(user=user)
    child_registrations = household_pool.filter(user_id__in=child_ids)

    context = {
        "title": "Upcoming Events",
        "personal_registrations": personal_registrations,
        "has_children": len(child_ids) > 0,
        "child_registrations": child_registrations,
    }
    return render(request, "accounts/upcoming_events.html", context)


@login_required
def outstanding_balance_view(request):
    user = request.user
    now = timezone.now()

    child_ids = list(user.child_accounts.values_list("id", flat=True))
    household_ids = [user.id] + child_ids

    # The Precise Balance Logic:
    # 1. Must be INCOMPLETE or have no order attached.
    # 2. Must either be a FUTURE event, OR a PAST event where they actually checked in.
    outstanding_registrations = (
        EventRegistration.objects.filter(user_id__in=household_ids)
        .filter(Q(order__isnull=True) | Q(order__payment_status=PaymentStatus.INCOMPLETE))
        .filter(Q(event__start_time__gte=now) | Q(checked_in=True))
        .select_related("user", "event")
        .order_by("event__start_time")
    )

    # Calculate total balance due across all actionable items
    total_balance_cents = sum(reg.final_price_cents for reg in outstanding_registrations)
    total_balance = total_balance_cents / 100.0

    context = {
        "title": "Outstanding Household Balance",
        "outstanding_registrations": outstanding_registrations,
        "total_balance": total_balance,
    }
    return render(request, "accounts/outstanding_balance.html", context)
