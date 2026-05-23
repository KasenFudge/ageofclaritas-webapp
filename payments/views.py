from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Create your views here.
@login_required
def payment_start_view(request, registration_id):
    # Just a fast dummy view to catch the landing redirect
    return render(request, "payments/payment_start.html", {
        "title": "Online Payment Placeholder"
    })