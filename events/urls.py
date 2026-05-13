from django.urls import path

from rulebook.urls import app_name, urlpatterns
from . import views

app_name = 'events'
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("<slug:slug>/", views.EventDetailView.as_view(), name="event_detail"),
    path("<slug:slug>/register/", views.EventRegistrationView.as_view(), name="event_registration"),
]