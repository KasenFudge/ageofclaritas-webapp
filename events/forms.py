from django import forms

from .models import EventAttendee

class EventRegistrationForm(forms.ModelForm):
    # Override the arrival_time field to explicitly accept AM/PM formatting
    arrival_time = forms.TimeField(
        input_formats=['%I:%M %p', '%I:%M%p', '%H:%M'],
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 09:30 AM'}),
        label="Arrival Time"
    )

    PAYMENT_CHOICES = [
        ("online", "Pay online"),
        ("in_person", "Pay in person")
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        initial="online"
    )

    class Meta:
        model = EventAttendee
        # Add the fields to be processed upon submission
        fields = ["arrival_time", "payment_method"]

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        super().__init__(*args, **kwargs)
    
    # Could use clean to validate arrival time is within bounds of the event.