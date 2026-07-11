from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import CustomAuthenticationForm, CustomPasswordResetForm, CustomSetPasswordForm

app_name = "accounts"

urlpatterns = [
    # --- Login & Register ---
    path(
        "login/",
        auth_views.LoginView.as_view(authentication_form=CustomAuthenticationForm, template_name="accounts/login.html"),
        name="login",
    ),
    path("register/", views.UserRegistrationView.as_view(), name="register"),
    # --- Password Reset Flow ---
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            form_class=CustomPasswordResetForm,
            template_name="accounts/password_reset_form.html",
            email_template_name="emails/password_reset_email.html",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=CustomSetPasswordForm,
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    # --- Dashboard ---
    path("dashboard/", views.account_dashboard_view, name="dashboard"),
    path("dashboard/settings/", views.update_account_settings_view, name="update_settings"),
    path("dashboard/sign-waiver/", views.sign_waiver_view, name="sign_waiver"),
]
