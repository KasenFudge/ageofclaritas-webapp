from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import CustomAuthenticationForm

app_name = "accounts"
urlpatterns = [
    path("login/", auth_views.LoginView.as_view(authentication_form=CustomAuthenticationForm), name="login"),
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    path("dashboard/", views.account_dashboard_view, name="dashboard"),
    path("dashboard/settings/", views.update_account_settings_view, name="update_settings"),
    path("dashboard/sign-waiver/", views.sign_waiver_view, name="sign_waiver"),
]
