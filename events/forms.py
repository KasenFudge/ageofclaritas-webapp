from datetime import date, datetime, time, timedelta

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

# Dropdown arrows use an Alpine.js-rotated SVG sibling, opening on focus and closing on blur,
# value change, or a forced blur on click. Reselecting the same unchanged value cannot be detected
# by browsers, so the chevron won't un-rotate until focus shifts away.
SELECT_CLASSES = f"{TEXT_INPUT_CLASSES} themed-select"
SELECT_ALPINE_ATTRS = {
    "@focus": "open = true",
    "@blur": "open = false",
    "@change": "open = false",
    "@mousedown": "if ($el === document.activeElement) { $event.preventDefault(); $el.blur(); }",
}


def _ordinal_suffix(day):
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _event_day_choices(event):
    """Every calendar day the event spans, as (ISO date string, "Weekday, Month Dayth") choices"""
    current = timezone.localtime(event.start_time).date()
    last = timezone.localtime(event.end_time).date()

    choices = []
    while current <= last:
        label = f"{current.strftime('%A, %B')} {current.day}{_ordinal_suffix(current.day)}"
        choices.append((current.isoformat(), label))
        current += timedelta(days=1)

    return choices


class EventRegistrationForm(forms.ModelForm):
    # Arrival time is split into four explicit picker/select inputs
    # They're recombined into a single `declared_arrival_time` datetime in clean().
    arrival_date = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASSES, **SELECT_ALPINE_ATTRS}),
        label="Expected Arrival Date",
    )
    arrival_hour = forms.ChoiceField(
        choices=[(str(h), str(h)) for h in range(1, 13)],
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASSES, **SELECT_ALPINE_ATTRS}),
        label="Hour",
    )
    arrival_minute = forms.ChoiceField(
        choices=[("00", "00"), ("15", "15"), ("30", "30"), ("45", "45")],
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASSES, **SELECT_ALPINE_ATTRS}),
        label="Minute",
    )
    arrival_period = forms.ChoiceField(
        choices=[("AM", "AM"), ("PM", "PM")],
        required=False,
        widget=forms.Select(attrs={"class": SELECT_CLASSES, **SELECT_ALPINE_ATTRS}),
        label="AM/PM",
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
        fields = ["weapon_rental"]

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        super().__init__(*args, **kwargs)

        # Already-flagged veterans don't need to be asked -- drop the field entirely so
        # there's nothing for the view to misinterpret if it's absent from cleaned_data.
        if self.user is not None and getattr(self.user, "is_veteran", False):
            del self.fields["is_first_event"]

        # The arrival date dropdown only offers days the event is actually happening --
        # has to be (re)built on every instantiation, not just when unbound, since
        # ChoiceField validates submitted values against self.fields[...].choices.
        if self.event is not None:
            self.fields["arrival_date"].choices = _event_day_choices(self.event)

        # Pre-fill the arrival fields to the event's actual start time on first load, so
        # a player who never touches them submits the correct value by default instead
        # of a blank widget they have to fill in (and could get wrong) from scratch.
        if not self.is_bound and self.event is not None:
            local_start = timezone.localtime(self.event.start_time)
            hour_24 = local_start.hour
            self.fields["arrival_date"].initial = local_start.date().isoformat()
            self.fields["arrival_hour"].initial = str(hour_24 % 12 or 12)
            self.fields["arrival_minute"].initial = f"{(local_start.minute // 15) * 15:02d}"
            self.fields["arrival_period"].initial = "PM" if hour_24 >= 12 else "AM"

    def clean(self):
        cleaned_data = super().clean()
        arrival_date = cleaned_data.get("arrival_date")
        arrival_hour = cleaned_data.get("arrival_hour")
        arrival_minute = cleaned_data.get("arrival_minute")
        arrival_period = cleaned_data.get("arrival_period")

        declared_arrival_time = None

        # Leaving the date blank keeps the "use the event's start time" default;
        # anything else requires all three time parts to be picked.
        if arrival_date:
            if arrival_hour and arrival_minute and arrival_period:
                hour_24 = int(arrival_hour) % 12
                if arrival_period == "PM":
                    hour_24 += 12
                naive = datetime.combine(
                    date.fromisoformat(arrival_date), time(hour=hour_24, minute=int(arrival_minute))
                )
                declared_arrival_time = timezone.make_aware(naive, timezone.get_current_timezone())
            else:
                self.add_error("arrival_date", "Please choose an hour, minute, and AM/PM for your arrival time.")

        cleaned_data["declared_arrival_time"] = declared_arrival_time

        # Bounds Validation: Verify the entire timestamp fits cleanly inside the event window
        if declared_arrival_time and self.event:
            if declared_arrival_time < self.event.start_time:
                self.add_error("arrival_date", "Your arrival time cannot be before the event officially begins.")

            if self.event.end_time and declared_arrival_time > self.event.end_time:
                self.add_error("arrival_date", "Your arrival time cannot be after the event has already ended.")

        return cleaned_data
