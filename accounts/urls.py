from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import CustomAuthenticationForm

app_name = "accounts"
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(authentication_form=CustomAuthenticationForm), name="login"),
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path("upcoming_events/", views.upcoming_events_view, name="upcoming_events"),
    path("outstanding_balance/", views.outstanding_balance_view, name="outstanding_balance"),
]
