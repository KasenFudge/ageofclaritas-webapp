from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path("upcoming_events/", views.upcoming_events_view, name="upcoming_events"),
    path("outstanding_balance/", views.outstanding_balance_view, name="outstanding_balance"),
]
