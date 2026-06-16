from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = "payments"
urlpatterns = [
    path("checkout/", views.checkout_page, name="checkout"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("success/", TemplateView.as_view(template_name="payments/success.html"), name="payment_success"),
]
