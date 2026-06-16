from django.urls import path

from . import views

app_name = "payments"
urlpatterns = [
    path("checkout/", views.checkout_page, name="checkout"),
    path("webhook/", views.stripe_webhook_handler, name="stripe_webhook"),
]
