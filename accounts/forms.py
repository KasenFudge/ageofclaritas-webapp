from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import CustomUser

# Matches the same widget-styling convention used in events/forms.py — the classes
# live on the widget itself so field_render.html never has to guess at markup.
TEXT_INPUT_CLASSES = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-navy-500 "
    "focus:outline-none focus:ring-1 focus:ring-navy-500"
)


class CustomAuthenticationForm(AuthenticationForm):
    """Styled login form. Django's built-in AuthenticationForm has no class
    applied to its widgets by default, so this exists purely to carry
    TEXT_INPUT_CLASSES the same way CustomUserCreationForm does below."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": TEXT_INPUT_CLASSES})


class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": TEXT_INPUT_CLASSES})

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = UserCreationForm.Meta.fields + (
            "email",
            "first_name",
            "last_name",
            "date_of_birth",
        )
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date"},  # This forces the native browser date picker
            ),
        }
