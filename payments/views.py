import stripe
from stripe import StripeClient
from django.conf import settings
from django.db import transaction
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from events.models import EventRegistration
from payments.models import Order, PaymentStatus

stripe_client = StripeClient(getattr(settings, "STRIPE_API_KEY", ""))

@login_required
def payment_start_view(request):
    user = request.user

    # 1. We expect a POST request containing the chosen registration IDs from checkboxes
    if request.method != "POST":
        # If they hit this via GET, redirect them back to their dashboard selection screen
        return redirect("accounts:upcoming_events")

    # Get the list of selected registration IDs from the form submission
    # <input type="checkbox" name="registration_ids" value="{{ reg.id }}">
    selected_ids = request.POST.getlist("registration_ids")

    if not selected_ids:
        # Handle case where they clicked submit without checking any boxes
        return redirect("accounts:upcoming_events")

    # 2. Security Boundary: Build the allowed household pool (Self + Children)
    authorized_user_ids = [user.id]
    child_ids = list(user.child_accounts.values_list('id', flat=True))
    authorized_user_ids.extend(child_ids)

    # 3. Fetch ONLY the requested registrations that belong to this household
    # This prevents malicious users from injecting random IDs into the POST data
    pending_registrations = EventRegistration.objects.filter(
        id__in=selected_ids,
        user_id__in=authorized_user_ids,
        is_manually_paid=False
    ).exclude(
        order__payment_status=PaymentStatus.COMPLETE
    )

    # If verification drops all rows (e.g. invalid IDs), fail safely
    if not pending_registrations.exists():
        return redirect("accounts:upcoming_events")

    # 4. Process the selected subset atomically
    with transaction.atomic():
        total_cents = sum(reg.final_price_cents for reg in pending_registrations)

        # Handle purely $0.00 selections safely
        if total_cents == 0:
            order = Order.objects.create(
                user=user,
                total_amount_cents=0,
                payment_status=PaymentStatus.COMPLETE
            )
            for reg in pending_registrations:
                reg.order = order
                reg.save()
            return redirect("payments:payment_success_view")

        # Create the standard pending umbrella Order
        order = Order.objects.create(
            user=user,
            total_amount_cents=total_cents,
            payment_status=PaymentStatus.PENDING
        )

        # Map the selected items to our transaction tracker
        for reg in pending_registrations:
            reg.order = order
            reg.save()

    # 5. Build dynamic line items for Stripe showing only selected individuals
    stripe_line_items = []
    for reg in pending_registrations:
        if reg.final_price_cents > 0:
            stripe_line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Pass: {reg.event.title}",
                        "description": f"Ticket for {reg.user.get_full_name() or reg.user.username}",
                    },
                    "unit_amount": reg.final_price_cents,
                },
                "quantity": 1,
            })

    # 6. Generate absolute return links
    success_url = request.build_absolute_uri(reverse("payment_success_view")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri(reverse("payment_cancel_view"))

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "payment_method_types": ["card"],
                "line_items": stripe_line_items,
                "mode": "payment",
                "metadata": {
                    "order_id": str(order.id), # Stripe API requires keys and values in metadata to be strings.
                    "user_id": str(user.id),
                },
                "success_url": success_url,
                "cancel_url": cancel_url,
            }
        )
        
        order.stripe_session_id = checkout_session.id
        order.save()

    except Exception as e:
        return render(request, "payments/payment_error.html", {"error": str(e)})

    return redirect(checkout_session.url, allow_external_redirect=True)

@csrf_exempt
@require_POST
def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)

    # Safety: If signature header or secret is missing, fail it immediately
    if not sig_header or not webhook_secret:
        return HttpResponse(status=400)

    try:
        # Construct the event using the initialized stripe_client object
        event = stripe_client.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # Handle the completed checkout event
    if event.type == "checkout.session.completed":
        # Collect information from the event to update our database.
        session = event.data.object
        metadata = getattr(session, "metadata", {})
        
        # Pull our custom order ID tracking flag out of the metadata dictionary
        order_id = metadata.get("order_id")

        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                if order.payment_status != PaymentStatus.COMPLETE:
                    order.payment_status = PaymentStatus.COMPLETE
                    order.save()
            except Order.DoesNotExist:
                pass

    return HttpResponse(status=200)

@login_required
def payment_success_view(request):
    # Stripe passes ?session_id={CHECKOUT_SESSION_ID} in the URL string.
    # We can grab it if we want to show a receipt later, but for now, 
    # we just want to tell the parent everything worked!
    session_id = request.GET.get("session_id")
    
    context = {
        "session_id": session_id,
    }
    return render(request, "payments/payment_success.html", context)


@login_required
def payment_cancel_view(request):
    # If a parent clicks the "Back" button inside Stripe Checkout,
    # they land here. We gracefully let them know nothing was charged.
    return render(request, "payments/payment_cancel.html")