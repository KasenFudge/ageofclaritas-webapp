from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import MINOR_SELF_SIGNUP_AGE, CustomUser

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


class UsernameRecoveryForm(forms.Form):
    """Asks for the email on an account so its username (and its children's) can be emailed there."""

    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"class": TEXT_INPUT_CLASSES})


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
        if age < MINOR_SELF_SIGNUP_AGE:
            raise ValidationError(
                f"You must be at least {MINOR_SELF_SIGNUP_AGE} to create your own account. If you're younger, "
                "a parent or guardian can create your account from theirs (Dashboard → Household)."
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


class ChildLoginForm(forms.Form):
    """
    The login half of a child's account: the username and password they sign in with,
    plus an optional email of their own. Used directly when a parent edits an existing
    child's login (or resets their password) from Household, and as the base of
    AddChildForm when adding a new child.
    """

    email = forms.EmailField(
        required=False,
        label="Their email (optional)",
        help_text="If given, they confirm it before logging in. Emails about them always go to you as well.",
    )
    username = forms.CharField(
        max_length=150,
        required=False,
        validators=[UnicodeUsernameValidator()],
        help_text="What they'll log in with.",
    )
    password1 = forms.CharField(
        label="Password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, child=None, **kwargs):
        # `child` is the existing account being edited, or None when adding a new one.
        self.child = child
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": TEXT_INPUT_CLASSES})
        if child is not None and not self.is_bound:
            self.initial.setdefault("username", child.username)
            if child.has_real_email:
                self.initial.setdefault("email", child.email)

    @property
    def password_required(self):
        # Editing a child who already has a password can leave it blank to keep it.
        return self.child is None or not self.child.has_usable_password()

    def _other_users(self):
        users = CustomUser.objects.all()
        if self.child is not None:
            users = users.exclude(pk=self.child.pk)
        return users

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        if email and self._other_users().filter(email__iexact=email).exists():
            self.add_error("email", "That email is already used by another account.")
        self._clean_login(cleaned_data)
        return cleaned_data

    def _clean_login(self, cleaned_data):
        username = cleaned_data.get("username")
        if not username:
            if "username" not in self.errors:
                self.add_error("username", "Choose a username for them to log in with.")
        elif self._other_users().filter(username__iexact=username).exists():
            self.add_error("username", "That username is already taken.")

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if not password1 and not password2:
            if self.password_required:
                self.add_error("password1", "Choose a password for them to log in with.")
            return
        if password1 != password2:
            self.add_error("password2", "The two passwords don't match.")
            return

        # Checked against a stand-in so the similarity validator compares against their names too
        candidate = self.child or CustomUser()
        try:
            password_validation.validate_password(
                password1,
                user=CustomUser(
                    username=username or candidate.username,
                    first_name=cleaned_data.get("first_name") or candidate.first_name,
                    last_name=cleaned_data.get("last_name") or candidate.last_name,
                    email=cleaned_data.get("email") or "",
                ),
            )
        except ValidationError as error:
            self.add_error("password1", error)


class AddChildForm(ChildLoginForm):
    """
    The one way a parent or guardian adds a child under 18 to their household, always
    with a login of their own. If the email entered already belongs to a teen who
    registered by themselves, no new account is made: `link_target` is set instead and
    the view sends that teen a guardian link request, so the other fields can be blank.
    """

    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    field_order = ["first_name", "last_name", "date_of_birth", "email", "username", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        # Shares the dashboard with the settings form, which has the same field names, so the
        # ids need their own namespace for each label to point at the right input.
        kwargs.setdefault("auto_id", "id_add_child_%s")
        super().__init__(*args, **kwargs)
        self.fields["email"].help_text = (
            "If given, they confirm it before logging in. Already made their own account? "
            "Enter its email and leave everything else blank to send them a link request."
        )
        self.link_target = None

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob is None:
            return dob
        today = timezone.localdate()
        if dob > today:
            raise ValidationError("Date of birth can't be in the future.")
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age >= 18:
            raise ValidationError("Only children under 18 can be added. Adults need an account of their own.")
        return dob

    def clean(self):
        # Skips ChildLoginForm.clean(): an existing email here means "link", not "taken".
        cleaned_data = forms.Form.clean(self)

        email = cleaned_data.get("email")
        existing = CustomUser.objects.filter(email__iexact=email).first() if email else None
        if existing is not None:
            if existing.age is None or existing.age >= 18:
                self.add_error("email", "That email belongs to an adult account, which can't be added as a child.")
            elif existing.parent_account_id is not None:
                self.add_error("email", f"{existing} is already linked to a parent or guardian.")
            elif existing.pending_guardian_id is not None:
                self.add_error("email", f"{existing} already has a guardian request waiting for their response.")
            else:
                self.link_target = existing
            return cleaned_data

        for name in ("first_name", "last_name", "date_of_birth"):
            if not cleaned_data.get(name) and name not in self.errors:
                self.add_error(name, "This field is required.")
        self._clean_login(cleaned_data)
        return cleaned_data
