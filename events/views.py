from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import request
from django.views.generic import DetailView, ListView, CreateView
from datetime import datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Event, EventType, EventRegistration
from .forms import EventRegistrationForm
from events.services.pricing import quote_price

# Macro to set the current app
def SetCurrentApp(context):
    context['current_app'] = 'events'

# Macro to set the title of the page
def SetPageTitle(context, title):
    context['title'] = title

# Create your views here.
class IndexView(ListView):
    model = Event
    template_name = "events/index.html"
    context_object_name = "events"

    # Get the events in the current year
    def get_queryset(self):
            year = timezone.now().year

            start = timezone.make_aware(datetime(year, 1, 1))
            end = timezone.make_aware(datetime(year + 1, 1, 1))

            # Grab the events within the defined range, then 
            return (
                 super()
                 .get_queryset()
                 .filter(start_time__gte=start, start_time__lt=end)
                 .order_by('start_time')
            )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        events = self.object_list

        context["senior_events"] = events.filter(event_type=EventType.SENIOR)
        context["junior_events"] = events.filter(event_type=EventType.JUNIOR)
        context["feast_events"] = events.filter(event_type=EventType.FEAST)
        context["other_events"] = events.filter(event_type=EventType.OTHER)

        SetCurrentApp(context)
        SetPageTitle(context, "Events")

        return context
    
class EventDetailView(DetailView):
    model = Event
    template_name = "events/event_detail.html"
    context_object_name = "event"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object

        # Give Context EventType for Comparison
        context['EventType'] = EventType

        SetCurrentApp(context)
        SetPageTitle(context, event.title)

        return context
    
@login_required
def event_registration_view(request, slug):
    # 1. Fetch target event data
    event = get_object_or_404(Event, slug=slug)
    user = request.user

    # 2. Enforce Age & Validation Safeguards
    if not user.date_of_birth:
        raise PermissionDenied("Birthdate required to register.")
    
    event_date = event.start_time.date()
    user_age = user.age_on(event_date)
    
    # TODO: This may need to be updated to allow parent accounts (accounts with child accounts) to register their children.
    if event.event_type == EventType.JUNIOR:
        if user_age < 8:
            raise PermissionDenied("Children must be 8 or older to register.")
        if user_age >= 18:
            raise PermissionDenied("Junior events are only for participants under 18.")
    
    if event.event_type == EventType.SENIOR and user_age < 18:
        raise PermissionDenied("Senior events are only for participants 18+.")

    # 3. Prevent Duplicate Registrations
    if EventRegistration.objects.filter(event=event, user=user).exists():
        messages.info(request, "You are already registered for this event.")
        return redirect("accounts:upcoming_events")

    # 4. Process Form Actions
    if request.method == "POST":
        # This forces the user's account to update its expiration records immediately
        student_discount = user.has_valid_student_discount

        # Pass event and user into form initialization (replacing get_form_kwargs)
        form = EventRegistrationForm(request.POST, event=event, user=user)
        
        if form.is_valid():
            arrival_time = form.cleaned_data.get("arrival_time") or event.start_time
            weapon_rental = form.cleaned_data.get("weapon_rental", False)
            payment_method = form.cleaned_data.get("payment_method", "cash")

            # Compute transaction parameters
            registration_time = timezone.now()
            quote = quote_price(
                event=event,
                user=user,
                registration_time=registration_time,
                arrival_time=arrival_time,
                student_discount=student_discount,
                weapon_rental=weapon_rental
            )

            # Build and decorate record payload
            registration = form.save(commit=False)
            registration.event = event
            registration.user = user
            registration.arrival_time = arrival_time

            # Apply calculated invoice rows
            registration.base_price_cents = quote.base_cents
            registration.final_price_cents = quote.final_cents
            registration.discounts = quote.discounts
            registration.additional_items = quote.additional_items
            
            # Commit record to db tables
            registration.save()

            # Dynamic checkout rerouting
            if payment_method == "online":
                return redirect("payments:payment_start", registration_id=registration.id)
            
            messages.success(request, f"Successfully registered for {event.title}!")
            return redirect("accounts:upcoming_events")
    else:
        # Evaluate student status on GET requests too so the database stays fresh
        _ = user.has_valid_student_discount
        # Build empty display form instance on safe GET request methods
        form = EventRegistrationForm(event=event, user=user)

    context = {
        "form": form,
        "event": event,
        "title": f"Register for {event.title}"
    }
    return render(request, "events/event_registration.html", context)