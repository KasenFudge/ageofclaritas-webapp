import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from events.models import EventRegistration

from .models import PaymentMethod, PaymentStatus, Transaction

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def checkout_page(request):
    """
    Renders the embedded Stripe checkout within the site's domain.
    """
    user = request.user
    now = timezone.now()

    # Gather the users ids as well as any child ids
    child_ids = list(user.child_accounts.values_list("id", flat=True))
    household_ids = [user.id] + child_ids

    # Gather the user's incomplete event registrations that need paid.
    # If they choose to pay online during registration process, this will just be the newly created registration.
    # The Precise Balance Logic:
    # 1. Must be INCOMPLETE or have no transaction attached.
    # 2. Must either be a FUTURE event, OR a PAST event where they actually checked in.
    outstanding_registrations = (
        EventRegistration.objects.filter(user_id__in=household_ids)
        .filter(Q(transaction__isnull=True) | Q(transaction__payment_status=PaymentStatus.INCOMPLETE))
        .filter(Q(event__start_time__gte=now) | Q(checked_in=True))
        .select_related("user", "event")
        .order_by("event__start_time")
    )

    # Fallback for if there is no registrations that need paid.
    if not outstanding_registrations.exists():
        # If they get here with nothing to pay, send them to show there is no outstanding balance.
        return redirect("accounts:outstanding_balance")

    # Sum up the exact outstanding cents from the unpaid registrations
    transaction_amount_cents = outstanding_registrations.aggregate(total=Sum("final_price_cents"))["total"] or 0

    # -------------------------------------------------------------
    # Check if an incomplete transaction already covers this exact batch
    # -------------------------------------------------------------
    # Check the first registration to see if it already points to an active, incomplete transaction
    first_reg = outstanding_registrations.first()
    existing_transaction = None

    if first_reg.transaction and first_reg.transaction.payment_status == PaymentStatus.INCOMPLETE:
        # Verify it matches the exact amount we expect to charge right now
        if first_reg.transaction.total_amount_cents == transaction_amount_cents:
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
            outstanding_registrations.update(transaction=transaction)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

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
    except stripe.error.SignatureVerificationError:
        # Cryptographic signature matching verification failed
        return HttpResponse(status=400)

    stripe_id = None
    target_status = None

    # 1. Handle Successful Payments
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        stripe_id = payment_intent["id"]
        target_status = PaymentStatus.COMPLETE

    # 2. Handle System Refunds
    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        stripe_id = charge["payment_intent"]
        target_status = PaymentStatus.REFUNDED

    # 3. Execute Database Updates
    if stripe_id and target_status:
        with db_transaction.atomic():
            try:
                # Find the local transaction matching Stripe's unique intent identifier
                local_transaction = Transaction.objects.select_for_update().get(stripe_session_id=stripe_id)

                # Update the status dynamically based on the event type
                if local_transaction.payment_status != target_status:
                    local_transaction.payment_status = target_status
                    local_transaction.save()
            except Transaction.DoesNotExist:
                # Log this error if a payment succeeded on Stripe but has no matching row in your system
                pass

    # Always return a 200 OK response to let Stripe know you safely received the message
    return HttpResponse(status=200)


@login_required
def payment_success_page(request):
    """
    Payment landing view that only allows people from a checkout session.
    """

    # Check if they have the active authorization token in their browser session from the checkout page.
    if "payment_intent_authorized" not in request.session:
        return redirect("accounts:outstanding_balance")

    # POP the token out of the session (If we decide to use it later)
    authorized_intent_id = request.session.pop("payment_intent_authorized")  # noqa: F841

    return render(request, "payments/success.html")
