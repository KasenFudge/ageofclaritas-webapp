from django.conf import settings
from django.db import models


# Create your models here.
class PaymentStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incomplete"
    COMPLETE = "complete", "Complete"
    REFUNDED = "refunded", "Refunded"


class PaymentMethod(models.TextChoices):
    ONLINE = "online", "Stripe Online"
    IN_PERSON = "in_person", "In Person at Event"


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_amount_cents = models.PositiveIntegerField()
    payment_status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INCOMPLETE,  # Default to Incomplete for unpaid tickets
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,  # Defaults to Online since users generate orders most often
    )
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user.username} ({self.payment_status})"
