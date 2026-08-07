from django import forms
from django.utils import timezone

from .models import EventRegistration

# Shared Tailwind widget styling. Defined once here so every widget stays visually
# consistent without field_render.html needing to guess at or reach into rendered HTML.
TEXT_INPUT_CLASSES = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-navy-500 "
    "focus:outline-none focus:ring-1 focus:ring-navy-500"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded accent-navy-600"
RADIO_CLASSES = "h-4 w-4 accent-navy-600"


class EventRegistrationForm(forms.ModelForm):
    declared_arrival_time = forms.DateTimeField(
        input_formats=[
            "%Y-%m-%dT%H:%M",  # Standard HTML5 datetime-local format (e.g., 2026-05-23T15:30)
            "%m/%d/%Y %I:%M %p",  # Standard text input format (e.g., 05/23/2026 03:30 PM)
            "%m/%d/%Y %H:%M",  # 24hr text variant
        ],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "autocomplete": "off", "class": TEXT_INPUT_CLASSES}
        ),
        label="Expected Arrival Date & Time",
        required=False,
        help_text="Leave blank if you plan to arrive when the event doors open.",
    )

    weapon_rental = forms.BooleanField(
        label="I need to rent weapons for this event",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
    )

    PAYMENT_CHOICES = [("online", "Pay online"), ("in_person", "Pay in person")]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect(attrs={"class": RADIO_CLASSES}),
        initial="online",
        help_text="Choose whether you'd like to pay online now or in person at the event.",
    )

    # A checkbox as one more confirmation for first_time discount. Meant to catch
    # old players using the new website for the first time.
    is_first_event = forms.BooleanField(
        label="This is my first Claritas event",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": CHECKBOX_CLASSES}),
        help_text=(
            "Uncheck this if you've attended an Age of Claritas event before -- even one that "
            "predates this website. This determines your first-time player discount."
        ),
    )

    class Meta:
        model = EventRegistration
        fields = ["declared_arrival_time", "weapon_rental"]

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        super().__init__(*args, **kwargs)

        # Already-flagged veterans don't need to be asked -- drop the field entirely so
        # there's nothing for the view to misinterpret if it's absent from cleaned_data.
        if self.user is not None and getattr(self.user, "is_veteran", False):
            del self.fields["is_first_event"]

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
