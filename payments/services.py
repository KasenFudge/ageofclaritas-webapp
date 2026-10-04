import logging

from django.db.models import Q
from django.utils import timezone

from events.models import EventRegistration

from .models import PaymentStatus

logger = logging.getLogger(__name__)

# Stripe won't create a USD charge below 50 cents.
STRIPE_MINIMUM_CHARGE_CENTS = 50


def get_outstanding_registrations(household_ids):
    """
    Registrations the household still owes money on. Shared by the dashboard balance and checkout
    so "Pay Now" always charges exactly what the dashboard shows.

    1. Must be INCOMPLETE/FAILED/CANCELED or have no transaction attached.
    2. Must either be for an event that hasn't ended yet, OR a past event they actually checked in to.
    3. Must actually cost something ($0 registrations are settled automatically).
    """
    return (
        EventRegistration.objects.filter(user_id__in=household_ids, final_price_cents__gt=0)
        .filter(
            Q(transaction__isnull=True)
            | Q(
                transaction__payment_status__in=[
                    PaymentStatus.INCOMPLETE,
                    PaymentStatus.FAILED,
                    PaymentStatus.CANCELED,
                ]
            )
        )
        .filter(Q(event__end_time__gte=timezone.now()) | Q(checked_in=True))
        .select_related("user", "event", "transaction")
        .order_by("event__start_time")
    )


def record_refund(transaction, total_refunded_cents):
    """
    Records the running refund total for a payment (Stripe reports it cumulatively) and assigns it to
    registrations wherever that's unambiguous:
      - a full refund covers every registration on the payment
      - a refund on a payment covering a single registration can only be for that registration
    A partial refund on a household payment is left for staff to assign in the registration admin.
    """
    now = timezone.now()
    total_refunded_cents = min(total_refunded_cents, transaction.total_amount_cents)
    fully_refunded = total_refunded_cents >= transaction.total_amount_cents

    transaction.refunded_amount_cents = total_refunded_cents
    transaction.refunded_at = now
    # A partial refund leaves the payment SUCCEEDED; only money fully returned counts as REFUNDED
    if fully_refunded:
        transaction.payment_status = PaymentStatus.REFUNDED
    transaction.save(update_fields=["refunded_amount_cents", "refunded_at", "payment_status"])

    registrations = list(transaction.registrations.all())
    if fully_refunded:
        allocations = {reg: reg.final_price_cents for reg in registrations}
    elif len(registrations) == 1:
        allocations = {registrations[0]: min(total_refunded_cents, registrations[0].final_price_cents)}
    else:
        logger.warning(
            "Partial refund of %s cents on Transaction #%s covers %s registrations - assign it in admin",
            total_refunded_cents,
            transaction.pk,
            len(registrations),
        )
        return

    for registration, refunded_cents in allocations.items():
        if registration.refunded_cents != refunded_cents:
            registration.refunded_cents = refunded_cents
            registration.refunded_at = now
            registration.save(update_fields=["refunded_cents", "refunded_at"])
