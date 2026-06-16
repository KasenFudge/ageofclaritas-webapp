from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# --- Events ---
class EventType(models.TextChoices):
    SENIOR = "senior", "Senior"
    JUNIOR = "junior", "Junior"
    FEAST = "feast", "Feast"
    OTHER = "other", "Other"


# --- Event Time Macros ---
def default_start_time():
    now = timezone.now()
    nine_am = datetime.combine(now.date(), time(hour=9))
    return timezone.make_aware(nine_am)


def default_end_time():
    now = timezone.now()
    four_pm_tomorrow = datetime.combine(now.date() + timedelta(days=1), time(hour=16))
    return timezone.make_aware(four_pm_tomorrow)


def default_downtime_due():
    now = timezone.now()
    two_weeks_later = datetime.combine(now.date() + timedelta(weeks=2, days=1), time(hour=23, minute=59, second=59))
    return timezone.make_aware(two_weeks_later)


# --- Image Upload Path Macros ---
def _upload_path(instance, filename, subdir=""):
    event = getattr(instance, "event", instance)
    slug = getattr(event, "slug", "untitled")
    base = f"images/Events/{slug}"
    if subdir:
        base = f"{base}/{subdir}"
    return f"{base}/{filename}"


def upload_event_main(instance, filename):
    return _upload_path(instance, filename)


def upload_event_album(instance, filename):
    return _upload_path(instance, filename, "EventAlbum")


class Event(models.Model):
    # Removed unique=True to support matching Junior and Senior named operations
    title = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60, blank=True, db_index=True)

    event_type = models.CharField(max_length=10, choices=EventType.choices, default=EventType.OTHER)
    base_price_cents = models.IntegerField(help_text="Base price of a ticket for the event before discounts in cents.")
    registration_available = models.BooleanField(
        default=True,
        help_text="Disables registration buttons if unchecked while allowing information for events to be shared.",
    )

    start_time = models.DateTimeField(default=default_start_time)
    end_time = models.DateTimeField(default=default_end_time)
    downtime_due = models.DateTimeField(
        default=default_downtime_due,
        help_text="This is the date by which attendees of the event must respond to the post event survey.",
    )

    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, through="EventRegistration", related_name="events")

    event_image = models.ImageField(upload_to=upload_event_main, blank=True)
    photographer = models.CharField(max_length=50, null=True, blank=True)

    # DYNAMIC INTERCEPT PROPERTY (TBA Layout handling)
    @property
    def display_title(self) -> str:
        """
        If registration is closed/hidden, intercept and mask the title safely as TBA
        without changing administrative historical names in the database.
        """
        if not self.registration_available:
            return "To Be Announced"
        return self.title

    def __str__(self):
        # Admin backend panel always sees the actual operational text layout
        return f"{self.title} ({self.get_event_type_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            # Append event type to slug processing routine to isolate URLs uniquely
            self.slug = slugify(f"{self.title}-{self.event_type}-")
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-start_time"]
        constraints = [
            # Title & Slug are unique within their specific Event Category Type group
            models.UniqueConstraint(fields=["title", "event_type"], name="unique_title_per_event_type"),
            models.UniqueConstraint(fields=["slug", "event_type"], name="unique_slug_per_event_type"),
        ]


class EventPriceTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="price_tiers")
    label = models.CharField(max_length=30)
    min_age = models.PositiveSmallIntegerField(help_text="Lower Age Requirement for this tier.")
    max_age = models.PositiveSmallIntegerField(help_text="Upper Age Requirement for this tier.")
    price_cents = models.PositiveIntegerField(help_text="Base price in cents.")


class EventRegistration(models.Model):
    # Relations for MANY-TO-MANY
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registrations")

    # Day of Event Administration
    checked_in = models.BooleanField(default=False)
    declared_arrival_time = models.DateTimeField()
    actual_arrival_time = models.DateTimeField(blank=True, null=True)

    # Ticket Pricing Information
    base_price_cents = models.PositiveIntegerField(help_text="Base price before discounts, in cents")
    final_price_cents = models.PositiveIntegerField(help_text="Final price charged, in cents")
    discounts = models.JSONField(default=list, blank=True)
    additional_items = models.JSONField(default=list, blank=True)

    # Information for making payments
    transaction = models.ForeignKey(
        "payments.Transaction",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="registrations",
        help_text="The parent transaction cart used to clear this registration online.",
    )

    @property
    def is_paid(self) -> bool:
        """Returns True if the linked transaction exists and is marked complete"""
        return self.transaction is not None and self.transaction.payment_status == "complete"

    @property
    def is_refunded(self) -> bool:
        """Returns True if the linked transaction exists and is marked refunded"""
        return self.transaction is not None and self.transaction.payment_status == "refunded"

    # Helper properties used in displaying pricing information in templates
    @property
    def base_price(self):
        return self.base_price_cents / 100.0

    @property
    def final_price(self):
        return self.final_price_cents / 100.0

    @property
    def formatted_discounts(self):
        """Converts internal discount information into a clean, easily used format"""
        return [{"type": d["type"], "amount": d["amount_cents"] / 100.0, "reason": d["reason"]} for d in self.discounts]

    @property
    def formatted_additional_items(self):
        """Converts internal additional items information into a clean, easily used format"""
        return [
            {"type": i["type"], "amount": i["amount_cents"] / 100.0, "reason": i["reason"]}
            for i in self.additional_items
        ]

    def __str__(self):
        return f"{self.user} - {self.event}"

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="unique_registration")]

    def save(self, *args, **kwargs):
        if not self.declared_arrival_time and self.event:
            self.declared_arrival_time = self.event.start_time
        super().save(*args, **kwargs)


class EventMedia(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="pictures")
    image = models.ImageField(upload_to=upload_event_album)
    alt_text = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Picture"
        verbose_name_plural = "Pictures"
