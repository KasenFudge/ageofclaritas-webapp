from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import CustomUser

# Matches the same widget-styling convention used in events/forms.py — the classes
# live on the widget itself so field_render.html never has to guess at markup.
TEXT_INPUT_CLASSES = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
    "text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-navy-500 "
    "focus:outline-none focus:ring-1 focus:ring-navy-500"
)


class CustomAuthenticationForm(AuthenticationForm):
    """
    Styled login form. Django's built-in AuthenticationForm has no class
    applied to its widgets by default, so this exists purely to carry
    TEXT_INPUT_CLASSES the same way CustomUserCreationForm does below.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": TEXT_INPUT_CLASSES})


class CustomPasswordResetForm(PasswordResetForm):
    """
    Styled password reset form. Django's built-in AuthenticationForm has no
    class applied to its widgets by default, so this exists purely to carry
    TEXT_INPUT_CLASSES the same way CustomUserCreationForm does below.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({"class": TEXT_INPUT_CLASSES})


class CustomSetPasswordForm(SetPasswordForm):
    """
    Styled password reset form. Django's built-in AuthenticationForm has no
    class applied to its widgets by default, so this exists purely to carry
    TEXT_INPUT_CLASSES the same way CustomUserCreationForm does below.
    """

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

    def clean_date_of_birth(self):
        dob = self.cleaned_data["date_of_birth"]
        today = timezone.localdate()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 14:
            raise ValidationError(
                "You must be at least 14 to create your own account. If you're under 14, "
                "ask a parent or guardian to add you as a dependent from their account dashboard."
            )
        return dob


class AccountSettingsForm(forms.ModelForm):
    """Basic profile fields a player can self-edit from the account dashboard.
    Deliberately excludes username, password, is_student, is_veteran, and
    parent_account — those are either admin-managed or need their own
    dedicated, more careful flow (password change in particular)."""

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "email", "date_of_birth"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": TEXT_INPUT_CLASSES})


class AddDependentForm(forms.ModelForm):
    """Lets a verified adult add a dependent (13 and under) profile from their
    dashboard. No login is ever created for this profile — see add_dependent_view."""

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "date_of_birth"]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": TEXT_INPUT_CLASSES})


class GuardianLinkRequestForm(forms.Form):
    """Lets a verified adult request to become the guardian of an existing teen
    (14-17) account. The teen must approve before the link takes effect."""

    identifier = forms.CharField(label="Teen's username or email", max_length=150)

    def __init__(self, *args, requesting_user=None, **kwargs):
        self.requesting_user = requesting_user
        super().__init__(*args, **kwargs)
        self.fields["identifier"].widget.attrs.update({"class": TEXT_INPUT_CLASSES})

    def clean_identifier(self):
        value = self.cleaned_data["identifier"].strip()
        try:
            target = CustomUser.objects.get(Q(username__iexact=value) | Q(email__iexact=value))
        except CustomUser.DoesNotExist:
            raise ValidationError("No account found with that username or email.")
        except CustomUser.MultipleObjectsReturned:
            raise ValidationError("That identifier matches more than one account; use the exact username.")

        if target.id == self.requesting_user.id:
            raise ValidationError("You cannot request yourself as a dependent.")
        if not target.has_usable_password():
            raise ValidationError("That account can't be linked this way.")
        if target.age is not None and target.age >= 18:
            raise ValidationError("Only minor accounts (under 18) can be linked via a guardian request.")
        if target.parent_account_id is not None:
            raise ValidationError(f"{target} already has a confirmed guardian on file.")
        if target.pending_guardian_id is not None:
            raise ValidationError(f"{target} already has a pending guardian request awaiting their response.")

        self.target_user = target
        return value
