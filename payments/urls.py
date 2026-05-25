from django.urls import path
from . import views

app_name = "payments"
urlpatterns = [
    # Where the form POSTs to start checkout
    path("checkout/", views.payment_start_view, name="payment_start_view"),
    
    # The backend destination path
    path("webhook/", views.stripe_webhook_view, name="stripe_webhook"),
    
    # The user landing pages after Stripe bounces them back
    path("success/", views.payment_success_view, name="payment_success_view"),
    path("cancel/", views.payment_cancel_view, name="payment_cancel_view"),
]