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

    # Build a human readable transaction description
    event_titles = ", ".join(list(set([str(reg.event) for reg in outstanding_registrations])))
    stripe_description = f"Event Registration Payment: {user} - {event_titles}"

    try:
        # Initialize the Payment Intent with Stripe
        intent = stripe.PaymentIntent.create(
            amount=transaction_amount_cents,
            currency="usd",
            description=stripe_description,
            metadata={"user_id": request.user.id},
        )

        # Create the local tracking Transaction model.
        transaction = Transaction.objects.create(
            total_amount_cents=transaction_amount_cents,
            payment_status=PaymentStatus.INCOMPLETE,
            payment_method=PaymentMethod.ONLINE,
            stripe_session_id=intent.id,
        )

        # Update all the outstanding registrations to point to this transaction
        outstanding_registrations.update(transaction=transaction)

        context = {
            "client_secret": intent.client_secret,
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "transaction_id": transaction.id,
            "amount_display": f"{transaction_amount_cents / 100:.2f}",
        }
        return render(request, "payments/checkout.html", context)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


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
    # Handle the specific payment intent success signal
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        stripe_id = payment_intent["id"]

        with db_transaction.atomic():
            try:
                # Find the local transaction matching Stripe's unique intent identifier
                local_transaction = Transaction.objects.select_for_update().get(stripe_session_id=stripe_id)

                # If it's already marked complete (e.g., from a duplicate hook), we can skip safely
                if local_transaction.payment_status != PaymentStatus.COMPLETE:
                    local_transaction.payment_status = PaymentStatus.COMPLETE
                    local_transaction.save()
            except Transaction.DoesNotExist:
                # Log this error if a payment succeeded on Stripe but has no matching row in your system
                pass

    # Always return a 200 OK response to let Stripe know you safely received the message
    return HttpResponse(status=200)
