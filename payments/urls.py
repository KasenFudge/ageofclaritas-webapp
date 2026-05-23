from django.urls import path
from . import views

app_name = "payments"
urlpatterns = [
    path("start/<int:registration_id>/", views.payment_start_view, name="payment_start"),
]