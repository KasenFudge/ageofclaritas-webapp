from django.db import models
from django.conf import settings

# Create your models here.
class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETE = "complete", "Complete"
    REFUNDED = "refunded", "Refunded"

class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="orders"
    )

    stripe_session_id = models.CharField(
        max_length=255, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="The unique identifier tracking this transaction on Stripe's servers"
    )

    total_amount_cents = models.PositiveIntegerField(
        help_text="The combined sum of all attached registrations in this specific transaction"
    )

    payment_status = models.CharField(
        max_length=10, 
        choices=PaymentStatus.choices, 
        default=PaymentStatus.PENDING
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} ({self.payment_status})"