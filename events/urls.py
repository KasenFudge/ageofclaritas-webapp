from django.urls import path

from . import views

app_name = "events"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("<slug:slug>/", views.EventDetailView.as_view(), name="detail"),
    path("<slug:slug>/register/", views.event_registration_view, name="register"),
]
