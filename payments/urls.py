from django.urls import path

from . import views

app_name = "payments"
urlpatterns = [
    path("checkout/", views.checkout_page, name="checkout"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("success/", views.payment_success_page, name="payment_success"),
]
