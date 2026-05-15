from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import request
from django.views.generic import DetailView, ListView, CreateView
from datetime import datetime
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.contrib import messages

from .models import Event, EventType, EventAttendee
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
    
class EventRegistrationView(LoginRequiredMixin, CreateView):
    model = EventAttendee
    form_class = EventRegistrationForm
    template_name = "events/event_registration.html"
    
    def dispatch(self, request, *args, **kwargs):
        self.event = get_object_or_404(Event, slug=kwargs["slug"])

        user = request.user
        if not user.date_of_birth:
            raise PermissionDenied("Birthdate required to register.")
        event_date = self.event.start_time.date()
        
        user_age = user.age_on(event_date)
        # TODO: This may need to be updated to allow accounts with child accounts to register their children.
        if self.event.event_type == EventType.JUNIOR:
            if user_age < 8:
                raise PermissionDenied("Children must be 8 or older to register.")
        
            if user_age >= 18:
                raise PermissionDenied("Junior events are only for participants under 18.")
        
        if self.event.event_type == EventType.SENIOR and user_age < 18:
            raise PermissionDenied("Senior events are only for participants 18+.")

        return super().dispatch(request, *args, **kwargs)
    
    # For FormView
    # def get_context_data(self, **kwargs):
    #      return super().get_context_data(**kwargs)
    
    # For CreateView
    def get_form_kwargs(self):
         kwargs = super().get_form_kwargs()
         kwargs["event"] = self.event
         kwargs["user"] = self.request.user
         return kwargs

    def form_valid(self, form):
        user = self.request.user

        # Stops duplicate registrations:
        if EventAttendee.objects.filter(event=self.event, user=user).exists():
            messages.info(self.request, "You are already registered for this event.")
            return redirect("accounts:upcoming_events")

        # Collect form data:
        arrival_time = form.cleaned_data["arrival_time"]
        student_discount = form.cleaned_data["student_discount"]
        weapon_rental = form.cleaned_data["weapon_rental"]
        payment_method = form.cleaned_data["payment_method"]

        # Get the time at registration:
        registration_time = timezone.now()

        # Compute price quote:
        quote = quote_price(
            event=self.event,
            user=user,
            registration_time=registration_time,
            arrival_time=arrival_time,
            student_discount=student_discount,
            weapon_rental=weapon_rental
        )

        # Create the attendee record:
        attendee = form.save(commit=False)
        attendee.event = self.event
        attendee.user = user

        # Store pricing information:
        attendee.base_price_cents = quote.base_cents
        attendee.final_price_cents = quote.final_cents
        attendee.discounts = quote.discounts
        attendee.additional_items = quote.additional_items

        # Write the row to the database
        attendee.save()

        if payment_method == "online":
            return redirect("accounts:payment_start", attendee_id=attendee.id) # Stand in redirect, adjust when making payment pages
        
        return redirect("accounts:upcoming_events")