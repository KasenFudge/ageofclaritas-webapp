import secrets

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# Promo code alphabet: uppercase letters and digits minus look-alikes (O/0, I/1/L)
# so codes read back cleanly when copied off a screen or a printed card.
PROMO_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_promo_code(length=10):
    return "".join(secrets.choice(PROMO_CODE_ALPHABET) for _ in range(length))


def normalize_code(code):
    """Codes are stored uppercase and matched case-insensitively."""
    return (code or "").strip().upper()


# Create your models here.
class PaymentStatus(models.TextChoices):
    INCOMPLETE = "incomplete", "Incomplete"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class PaymentMethod(models.TextChoices):
    ONLINE = "online", "Stripe Online"
    IN_PERSON = "in_person", "In Person at Event"


class Transaction(models.Model):
    total_amount_cents = models.PositiveIntegerField()
    payment_status = models.CharField(
        max_length=15,
        choices=PaymentStatus.choices,
        default=PaymentStatus.INCOMPLETE,  # Default to Incomplete for unpaid tickets
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,  # Defaults to Online since users generate payments most often
    )
    stripe_session_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Safely grab the first registration if it exists
        first_reg = self.registrations.first()
        user_display = first_reg.user.username if first_reg else "No User"

        return f"Transaction #{self.id} - {user_display} ({self.get_payment_status_display()})"


class Voucher(models.Model):
    """A one-time-use code that covers the full ticket price of a single event registration."""

    code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        help_text="Leave blank to auto-generate a random code. Codes are not case-sensitive.",
    )
    note = models.CharField(max_length=200, blank=True, help_text="Who this voucher is for and why (admin only).")
    created_at = models.DateTimeField(auto_now_add=True)

    # Clearing used_at re-issues the voucher (e.g. after a refund).
    used_at = models.DateTimeField(
        null=True, blank=True, help_text="When this voucher was redeemed. Clear this to make it usable again."
    )
    used_by_registration = models.ForeignKey(
        "events.EventRegistration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vouchers_used",
    )

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    def clean(self):
        # Normalize before the admin's uniqueness check so "abc" can't slip past an existing "ABC"
        self.code = normalize_code(self.code)
        if self.code and Promotion.objects.filter(code=self.code).exists():
            raise ValidationError({"code": "A promotion already uses this code."})

    def save(self, *args, **kwargs):
        self.code = normalize_code(self.code)
        if not self.code:
            # Retry on the (very unlikely) collision with an existing voucher or promotion code
            while True:
                self.code = generate_promo_code()
                if not (
                    Voucher.objects.filter(code=self.code).exists() or Promotion.objects.filter(code=self.code).exists()
                ):
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Voucher {self.code} ({'Used' if self.is_used else 'Unused'})"


class Promotion(models.Model):
    """A reusable code that takes a percentage or flat amount off the ticket price until it expires."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percent Off"
        FLAT = "flat", "Flat Amount Off"

    code = models.CharField(max_length=32, unique=True, help_text="The code players enter. Not case-sensitive.")
    name = models.CharField(max_length=100, help_text="Shown to players as the discount reason.")
    discount_type = models.CharField(max_length=10, choices=DiscountType.choices, default=DiscountType.PERCENT)
    percent_off = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Percent off the ticket (1-100). Only for Percent Off promotions.",
    )
    amount_off_cents = models.PositiveIntegerField(
        null=True, blank=True, help_text="Amount off the ticket in cents. Only for Flat Amount Off promotions."
    )
    starts_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(
        null=True, blank=True, help_text="Leave blank to run until the promotion is manually deactivated."
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to shut this promotion off immediately.")

    @property
    def is_currently_valid(self) -> bool:
        now = timezone.now()
        return self.is_active and self.starts_at <= now and (self.expires_at is None or self.expires_at > now)

    def discount_for(self, subtotal_cents):
        """Discount against the ticket price remaining after all other discounts."""
        if self.discount_type == self.DiscountType.PERCENT:
            return subtotal_cents * (self.percent_off or 0) // 100
        return min(self.amount_off_cents or 0, subtotal_cents)

    def clean(self):
        errors = {}
        if self.discount_type == self.DiscountType.PERCENT:
            if self.percent_off is None:
                errors["percent_off"] = "Required for Percent Off promotions."
            if self.amount_off_cents is not None:
                errors["amount_off_cents"] = "Leave blank for Percent Off promotions."
        else:
            if self.amount_off_cents is None:
                errors["amount_off_cents"] = "Required for Flat Amount Off promotions."
            if self.percent_off is not None:
                errors["percent_off"] = "Leave blank for Flat Amount Off promotions."

        if self.expires_at and self.starts_at and self.expires_at <= self.starts_at:
            errors["expires_at"] = "Must be after the start time."

        self.code = normalize_code(self.code)
        if self.code and Voucher.objects.filter(code=self.code).exists():
            errors["code"] = "A voucher already uses this code."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.code = normalize_code(self.code)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"
