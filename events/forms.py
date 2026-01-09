from django import forms

from .models import EventAttendee

class EventRegistrationForm(forms.ModelForm):
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
        fields = ["arrival_time"]

    def __init__(self, *args, event=None, user=None, **kwargs):
        self.event = event
        self.user = user
        return super().__init__(*args, **kwargs)
    
    # Could use clean to validate arrival time is within bounds of the event.