from django import forms
from django.utils import timezone

from .models import EventRegistration


class EventRegistrationForm(forms.ModelForm):
    declared_arrival_time = forms.DateTimeField(
        input_formats=[
            "%Y-%m-%dT%H:%M",  # Standard HTML5 datetime-local format (e.g., 2026-05-23T15:30)
            "%m/%d/%Y %I:%M %p",  # Standard text input format (e.g., 05/23/2026 03:30 PM)
            "%m/%d/%Y %H:%M",  # 24hr text variant
        ],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",  # Triggers the native browser interactive calendar/clock picker
                "class": "form-control",
            }
        ),
        label="Expected Arrival Date & Time",
        required=False,
        help_text="Leave blank if you plan to arrive when the event doors open.",
    )

    weapon_rental = forms.BooleanField(
        label="I need to rent weapons for this event",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    PAYMENT_CHOICES = [("online", "Pay online"), ("in_person", "Pay in person")]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES, widget=forms.RadioSelect(attrs={"class": "form-check-input"}), initial="online"
    )

    class Meta:
        model = EventRegistration
        fields = ["declared_arrival_time", "weapon_rental"]

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        declared_arrival_time = cleaned_data.get("declared_arrival_time")

        # Bounds Validation: Verify the entire timestamp fits cleanly inside the event window
        if declared_arrival_time and self.event:
            # Safely handle timezone boundaries if the input is naive
            if timezone.is_naive(declared_arrival_time):
                declared_arrival_time = timezone.make_aware(declared_arrival_time, timezone.get_current_timezone())

            if declared_arrival_time < self.event.start_time:
                self.add_error(
                    "declared_arrival_time", "Your arrival time cannot be before the event officially begins."
                )

            if self.event.end_time and declared_arrival_time > self.event.end_time:
                self.add_error(
                    "declared_arrival_time", "Your arrival time cannot be after the event has already ended."
                )

        return cleaned_data
