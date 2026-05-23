from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Create your views here.
@login_required
def upcoming_events_view(request):
    # Just a fast dummy view to catch the landing redirect
    return render(request, "accounts/upcoming_events.html", {
        "title": "Upcoming Events Dashboard Placeholder"
    })