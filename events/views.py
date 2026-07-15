from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView

from events.services.pricing import quote_price

from .forms import EventRegistrationForm
from .models import Event, EventRegistration, EventType


# Create your views here.
class IndexView(ListView):
    model = Event
    template_name = "events/index.html"
    context_object_name = "events"

    # Get the events in the current year
    def get_queryset(self):
        """
        Returns all future events sorted chronologically,
        ensuring an evergreen timeline for the players.
        """
        return super().get_queryset().filter(end_time__gt=timezone.now()).order_by("start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        events = self.object_list

        context["senior_events"] = events.filter(event_type=EventType.SENIOR)
        context["junior_events"] = events.filter(event_type=EventType.JUNIOR)
        context["feast_events"] = events.filter(event_type=EventType.FEAST)
        context["other_events"] = events.filter(event_type=EventType.OTHER)
        context["next_senior_event"] = context["senior_events"].first()
        context["next_junior_event"] = context["junior_events"].first()

        return context


class EventDetailView(DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Give Context EventType for Comparison
        context["EventType"] = EventType

        return context


@login_required
def event_registration_view(request, slug, user_id=None):
    # 1. Fetch target event data
    event = get_object_or_404(Event, slug=slug)
    actor = request.user  # The person sitting at the keyboard

    # 2. Determine the Target Participant
    if user_id and user_id != actor.id:
        # Fetch the child account, ensuring it actually belongs to this parent
        target_user = get_object_or_404(actor.child_accounts.all(), id=user_id)
    else:
        target_user = actor

    # 3. Enforce Age & Validation Safeguards on the Target User
    if not target_user.date_of_birth:
        raise PermissionDenied(f"Birthdate required to register {target_user}.")

    event_date = event.start_time.date()
    user_age = target_user.age_on(event_date)

    if event.event_type == EventType.JUNIOR:
        if user_age < 8:
            raise PermissionDenied(f"{target_user} must be 8 or older to register.")
        if user_age >= 18:
            raise PermissionDenied(f"Junior events are only for participants under 18 ({target_user} is {user_age}).")

    if event.event_type == EventType.SENIOR and user_age < 18:
        raise PermissionDenied(f"Senior events are only for participants 18+ ({target_user} is {user_age}).")

    # 4. Enforce Active Waiver Signature
    if not target_user.has_signed_active_waiver():
        messages.warning(
            request, f"An active liability waiver must be signed for {target_user} before completing registration."
        )
        return redirect("accounts:dashboard")

    # 5. Prevent Duplicate Registrations
    if EventRegistration.objects.filter(event=event, user=target_user).exists():
        messages.info(request, f"{target_user} is already registered for this event.")
        return redirect("accounts:dashboard")

    # 6. Process Form Actions
    if request.method == "POST":
        # Check discount matching the actual participant
        student_discount = target_user.has_valid_student_discount

        # Form initialization tailored to the target profile
        form = EventRegistrationForm(request.POST, event=event, user=target_user)

        if form.is_valid():
            declared_arrival_time = form.cleaned_data.get("declared_arrival_time") or event.start_time
            weapon_rental = form.cleaned_data.get("weapon_rental", False)
            payment_method = form.cleaned_data.get("payment_method", "in_person")

            # Self-reported "not my first event" - mark them as veteran for pricing so a first time discount
            # is not applied to their account and we don't ask them in the future.
            if form.cleaned_data.get("is_first_event") is False and not target_user.is_veteran:
                target_user.is_veteran = True
                target_user.save(update_fields=["is_veteran"])

            # Compute transaction details for the target attendee
            registration_time = timezone.now()
            quote = quote_price(
                event=event,
                user=target_user,
                registration_time=registration_time,
                arrival_time=declared_arrival_time,
                student_discount=student_discount,
                weapon_rental=weapon_rental,
            )

            registration = form.save(commit=False)
            registration.event = event
            registration.user = target_user  # Bound to the child/adult participant
            registration.declared_arrival_time = declared_arrival_time

            registration.base_price_cents = quote.base_cents
            registration.final_price_cents = quote.final_cents
            registration.discounts = quote.discounts
            registration.additional_items = quote.additional_items
            registration.save()

            if quote.final_cents == 0:
                from payments.models import Transaction

                zero_dollar_transaction = Transaction.objects.create(
                    total_amount_cents=0,
                    payment_status="succeeded",
                    payment_method="online" if payment_method == "online" else "in_person",
                )
                registration.transaction = zero_dollar_transaction
                registration.save()

                messages.success(
                    request,
                    f"Successfully registered {target_user} for {event.title} with First Event Discount Applied!",
                )
                return redirect("accounts:dashboard")

            if payment_method == "online":
                return redirect("payments:checkout")

            messages.success(request, f"Successfully registered {target_user} for {event.title}!")
            return redirect("accounts:dashboard")
    else:
        _ = target_user.has_valid_student_discount
        form = EventRegistrationForm(event=event, user=target_user)

    context = {"form": form, "event": event, "target_user": target_user}
    return render(request, "events/event_registration.html", context)
