from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import FormView, DetailView, ListView
from datetime import datetime
from django.utils import timezone

from .models import Event, EventType

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
    
class EventRegistrationView(LoginRequiredMixin, FormView):
    template_name = "events/event_registration.html"