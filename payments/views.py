import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch
from django.views.decorators.csrf import csrf_exempt

from events.models import EventRegistration

from .models import PaymentMethod, PaymentStatus, Transaction
from .services import STRIPE_MINIMUM_CHARGE_CENTS, get_outstanding_registrations, record_refund

stripe.api_key = settings.STRIPE_SECRET_KEY

logger = logging.getLogger(__name__)


NO_BALANCE_REDIRECT = "accounts:dashboard"


def _safe_redirect(request, url_name):
    """
    Redirect defensively: never let a bad/renamed URL name 500 a payment page.
    Falls back to the site root and logs loudly so it gets fixed instead of
    silently recurring.
    """
    try:
        return redirect(url_name)
    except NoReverseMatch:
        logger.error("Payment flow tried to redirect to unknown URL name %r", url_name)
        return redirect("/")


def _cancel_stale_payment_intents(registration_ids):
    """
    Cancels the Stripe PaymentIntents of any unpaid transactions these registrations are currently on,
    and marks those transactions CANCELED. Returns False (and changes nothing further) if one of them
    can't be canceled because the player has already paid it or the payment is still processing.
    """
    stale_transactions = Transaction.objects.filter(
        registrations__pk__in=registration_ids,
        payment_status__in=[PaymentStatus.INCOMPLETE, PaymentStatus.FAILED],
        stripe_session_id__isnull=False,
    ).distinct()

    for stale in stale_transactions:
        try:
            stripe.PaymentIntent.cancel(stale.stripe_session_id)
        except stripe.InvalidRequestError:
            # Stripe refuses to cancel intents that already succeeded, are processing, or were canceled
            intent = stripe.PaymentIntent.retrieve(stale.stripe_session_id)
            if intent.status != "canceled":
                logger.warning(
                    "Not replacing Transaction #%s: its PaymentIntent %s is %s",
                    stale.pk,
                    stale.stripe_session_id,
                    intent.status,
                )
                return False

        stale.payment_status = PaymentStatus.CANCELED
        stale.save(update_fields=["payment_status"])

    return True


@login_required
def checkout_page(request):
    """
    Renders the embedded Stripe checkout within the site's domain.
    """
    user = request.user

    # Gather the users ids as well as any child ids
    child_ids = list(user.child_accounts.values_list("id", flat=True))
    household_ids = [user.id] + child_ids

    # Gather the user's incomplete event registrations that need paid.
    # If they choose to pay online during registration process, this will just be the newly created registration.
    outstanding_registrations = get_outstanding_registrations(household_ids)

    # Fallback for if there is no registrations that need paid.
    if not outstanding_registrations.exists():
        # If they get here with nothing to pay, send them to show there is no outstanding balance.
        return _safe_redirect(request, NO_BALANCE_REDIRECT)

    # Sum up the exact outstanding cents from the unpaid registrations
    transaction_amount_cents = outstanding_registrations.aggregate(total=Sum("final_price_cents"))["total"] or 0

    # Stripe rejects charges this small, so don't even try.
    if transaction_amount_cents < STRIPE_MINIMUM_CHARGE_CENTS:
        messages.warning(
            request, "Your balance is below the minimum for online payment. Please settle it in person at the event."
        )
        return _safe_redirect(request, NO_BALANCE_REDIRECT)

    # Pin the batch now: canceling stale payments below changes transaction statuses, which would
    # otherwise change what the outstanding queryset matches when it's re-evaluated.
    registration_ids = list(outstanding_registrations.values_list("pk", flat=True))

    # -------------------------------------------------------------
    # Check if an incomplete transaction already covers this exact batch
    # -------------------------------------------------------------
    # Check the first registration to see if it already points to an active, incomplete transaction
    first_reg = outstanding_registrations.first()
    existing_transaction = None

    if first_reg.transaction and first_reg.transaction.payment_status == PaymentStatus.INCOMPLETE:
        # Verify it matches the exact amount we expect to charge right now, and that every outstanding
        # registration is on it (a matching total alone could hide a swapped-in registration)
        covers_whole_batch = not outstanding_registrations.exclude(transaction=first_reg.transaction).exists()
        if covers_whole_batch and first_reg.transaction.total_amount_cents == transaction_amount_cents:
            existing_transaction = first_reg.transaction

    if existing_transaction:
        # Reuse the existing intent to avoid cluttering the database or Stripe logs
        # We retrieve the active intent from Stripe to grab its fresh client_secret
        try:
            intent = stripe.PaymentIntent.retrieve(existing_transaction.stripe_session_id)
            transaction = existing_transaction
        except Exception:
            # Fallback if the intent expired on Stripe's end over time
            existing_transaction = None

    # If no valid existing transaction was found, create a brand new one
    if not existing_transaction:
        event_titles = ", ".join(list(set([str(reg.event) for reg in outstanding_registrations])))
        stripe_description = f"Event Registration Payment: {user} - {event_titles}"

        try:
            # Close out any older payment for these registrations first, so an old checkout tab
            # can't be paid into a transaction the registrations are no longer attached to.
            if not _cancel_stale_payment_intents(registration_ids):
                messages.info(
                    request,
                    "A payment for this balance is already being processed. Please check back in a few minutes.",
                )
                return _safe_redirect(request, NO_BALANCE_REDIRECT)

            intent = stripe.PaymentIntent.create(
                amount=transaction_amount_cents,
                currency="usd",
                description=stripe_description,
                metadata={"user_id": request.user.id},
            )

            transaction = Transaction.objects.create(
                total_amount_cents=transaction_amount_cents,
                payment_status=PaymentStatus.INCOMPLETE,
                payment_method=PaymentMethod.ONLINE,
                stripe_session_id=intent.id,
            )

            # Link this new transaction to the current registrations batch
            EventRegistration.objects.filter(pk__in=registration_ids).update(transaction=transaction)

        except Exception:
            # Never show a raw Stripe/DB error to the player; log it loudly and send them somewhere safe.
            logger.exception("Failed to create a Stripe PaymentIntent for user %s", user.id)
            messages.error(
                request,
                "We couldn't start your online payment right now. Please try again later or pay in person.",
            )
            return _safe_redirect(request, NO_BALANCE_REDIRECT)

    # -------------------------------------------------------------
    # Common Execution path for both fresh and reused sessions
    # -------------------------------------------------------------
    request.session["payment_intent_authorized"] = intent.id

    context = {
        "client_secret": intent.client_secret,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "transaction_id": transaction.id,
        "amount_display": f"{transaction_amount_cents / 100:.2f}",
    }
    return render(request, "payments/checkout.html", context)


@csrf_exempt
def stripe_webhook(request):
    """
    Listens for signals from stripe to capture completed transactions in real time
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    event = None

    try:
        # Construct and verify the event using Stripe's official library.
        # This prevents malicious actors from spoofing fake payments to the server.
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        # Invalid payload layout
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        # Cryptographic signature matching verification failed.
        # (stripe.error.SignatureVerificationError also works on current SDKs,
        # but the flat top-level name is the one that's guaranteed going forward.)
        return HttpResponse(status=400)
    except Exception:
        # Anything else here (a transient Stripe SDK error, etc.) must not bubble
        # up as a 500 - Stripe will keep retrying a 500 for days, but if the bug
        # is deterministic it'll just fail every retry too. Log it and 400 so it
        # shows up in monitoring instead of silently stalling the payment status.
        logger.exception("Unexpected error verifying Stripe webhook signature")
        return HttpResponse(status=400)

    stripe_id = None
    target_status = None
    refunded_cents = None

    # 1. Handle Successful Payments
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        stripe_id = payment_intent["id"]
        target_status = PaymentStatus.SUCCEEDED

    # 2. Handle Failed Payments
    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        stripe_id = payment_intent["id"]
        target_status = PaymentStatus.FAILED

    # 3. Handle System Refunds
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        stripe_id = charge["payment_intent"] if "payment_intent" in charge else None
        target_status = PaymentStatus.REFUNDED
        # Cumulative across every refund on this charge, so partial refunds are told apart from full ones
        refunded_cents = charge["amount_refunded"]

    # 4. Execute Database Updates
    if stripe_id and target_status:
        try:
            with db_transaction.atomic():
                # Find the local transaction matching Stripe's unique intent identifier
                local_transaction = Transaction.objects.select_for_update().get(stripe_session_id=stripe_id)

                # Refunds record the amount and assign it to registrations; full refunds also flip the status
                if refunded_cents is not None:
                    record_refund(local_transaction, refunded_cents)

                # Update the status dynamically based on the event type
                elif local_transaction.payment_status != target_status:
                    local_transaction.payment_status = target_status
                    local_transaction.save()

                # Money received for a transaction no registration points to means a player paid but
                # still looks unpaid - needs a human to reattach it.
                if target_status == PaymentStatus.SUCCEEDED and not local_transaction.registrations.exists():
                    logger.error(
                        "Payment succeeded for Transaction #%s (intent %s) but it has no registrations attached",
                        local_transaction.pk,
                        stripe_id,
                    )
        except Transaction.DoesNotExist:
            # This is exactly the "Stripe says paid, our DB disagrees" case -
            # it must be loud, not a silent pass, or it'll keep happening unnoticed.
            logger.error(
                "Stripe webhook %s for intent %s has no matching Transaction (target_status=%s)",
                event["type"],
                stripe_id,
                target_status,
            )
        except Transaction.MultipleObjectsReturned:
            logger.error(
                "Multiple Transactions share stripe_session_id=%s while handling %s - data integrity issue",
                stripe_id,
                event["type"],
            )

    # Always return a 200 OK response to let Stripe know you safely received the message
    return HttpResponse(status=200)


@login_required
def payment_success_page(request):
    """
    Payment landing view that only allows people from a checkout session.
    """

    # Check if they have the active authorization token in their browser session from the checkout page.
    if "payment_intent_authorized" not in request.session:
        return _safe_redirect(request, NO_BALANCE_REDIRECT)

    # POP the token out of the session (If we decide to use it later)
    authorized_intent_id = request.session.pop("payment_intent_authorized")  # noqa: F841

    return render(request, "payments/success.html")
