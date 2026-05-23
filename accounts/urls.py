from django.urls import path
from . import views

app_name = "accounts"
urlpatterns = [
    path("upcoming_events/", views.upcoming_events_view, name="upcoming_events")
]