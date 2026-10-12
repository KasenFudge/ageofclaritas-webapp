from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .forms import AddChildForm, ChildLoginForm, CustomUserCreationForm
from .models import Waiver, WaiverSignature
from .utils import dependent_placeholder_email, email_recipients, minor_waiver_message, send_to_household

User = get_user_model()

PASSWORD = "Sturdy-Lantern-42"


def born_years_ago(years):
    """A birthday that makes someone `years` old today and for the next few months."""
    today = timezone.localdate()
    return date(today.year - years, today.month, 1) - timedelta(days=200)


def make_user(username, age=36, **extra):
    extra.setdefault("email", f"{username}@example.test")
    return User.objects.create_user(username=username, password="test-pass", date_of_birth=born_years_ago(age), **extra)


def child_data(**overrides):
    data = {
        "first_name": "Robin",
        "last_name": "Hood",
        "date_of_birth": born_years_ago(10).isoformat(),
        "username": "robin",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "email": "",
    }
    data.update(overrides)
    return data


class SelfRegistrationAgeGateTests(TestCase):
    def form(self, age):
        return CustomUserCreationForm(
            {
                "username": f"player{age}",
                "email": f"player{age}@example.test",
                "first_name": "Pat",
                "last_name": "Player",
                "date_of_birth": born_years_ago(age).isoformat(),
                "password1": PASSWORD,
                "password2": PASSWORD,
            }
        )

    def test_twelve_year_old_cannot_self_register(self):
        form = self.form(12)
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_thirteen_year_old_can_self_register(self):
        self.assertTrue(self.form(13).is_valid())


class AddChildFormTests(TestCase):
    def test_valid_child(self):
        self.assertTrue(AddChildForm(child_data()).is_valid())

    def test_requires_login_and_details(self):
        form = AddChildForm(child_data(username="", password1="", password2="", first_name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("password1", form.errors)
        self.assertIn("first_name", form.errors)

    def test_rejects_adults(self):
        form = AddChildForm(child_data(date_of_birth=born_years_ago(18).isoformat()))
        self.assertFalse(form.is_valid())
        self.assertIn("date_of_birth", form.errors)

    def test_rejects_weak_or_mismatched_passwords(self):
        self.assertIn("password1", AddChildForm(child_data(password1="123", password2="123")).errors)
        self.assertIn("password2", AddChildForm(child_data(password2="Different-Lantern-42")).errors)

    def test_rejects_taken_username_case_insensitively(self):
        make_user("Robin")
        self.assertIn("username", AddChildForm(child_data()).errors)

    def test_rejects_emails_that_cannot_be_linked(self):
        adult = make_user("adult")
        linked = make_user("linked", age=15, parent_account=adult)
        for email in (adult.email, linked.email):
            with self.subTest(email=email):
                form = AddChildForm(child_data(email=email))
                self.assertFalse(form.is_valid())
                self.assertIn("email", form.errors)

    def test_unlinked_teen_email_becomes_a_link_request(self):
        teen = make_user("teen", age=15)
        form = AddChildForm({"email": teen.email.upper()})  # everything else left blank
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.link_target, teen)


class AddChildViewTests(TestCase):
    def setUp(self):
        self.parent = make_user("parent")
        self.client.force_login(self.parent)

    def post(self, **overrides):
        return self.client.post(reverse("accounts:add_child"), child_data(**overrides))

    def test_child_without_email_can_log_in_immediately(self):
        response = self.post()
        self.assertRedirects(response, f"{reverse('accounts:dashboard')}?open=household", fetch_redirect_response=False)

        child = User.objects.get(username="robin")
        self.assertEqual(child.parent_account, self.parent)
        self.assertTrue(child.is_active)
        self.assertFalse(child.has_real_email)
        self.assertEqual(child.email, dependent_placeholder_email("robin"))
        self.assertTrue(self.client.login(username="robin", password=PASSWORD))

        # Only the parent hears about it, since the child has no address
        self.assertEqual([m.to for m in mail.outbox], [[self.parent.email]])

    def test_child_with_email_logs_in_after_confirming(self):
        self.post(email="robin@example.test")

        child = User.objects.get(username="robin")
        self.assertFalse(child.is_active)
        self.assertFalse(self.client.login(username="robin", password=PASSWORD))
        self.assertCountEqual([m.to for m in mail.outbox], [[self.parent.email], ["robin@example.test"]])
        activation = next(m for m in mail.outbox if m.to == ["robin@example.test"])
        self.assertIn("parent created an Age of Claritas account for you", activation.body)

        uid = urlsafe_base64_encode(force_bytes(child.pk))
        token = default_token_generator.make_token(child)
        self.client.get(reverse("accounts:activate", args=[uid, token]))
        self.assertTrue(self.client.login(username="robin", password=PASSWORD))

    def test_unlinked_teen_email_sends_link_request_instead_of_creating(self):
        teen = make_user("teen", age=15)
        before = User.objects.count()
        self.client.post(reverse("accounts:add_child"), {"email": teen.email})

        teen.refresh_from_db()
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(teen.pending_guardian, self.parent)
        self.assertEqual([m.to for m in mail.outbox], [[teen.email]])

        # The teen approves from their own dashboard
        self.client.force_login(teen)
        self.client.post(reverse("accounts:respond_guardian_link"), {"action": "approve"})
        teen.refresh_from_db()
        self.assertEqual(teen.parent_account, self.parent)
        self.assertIsNone(teen.pending_guardian)

    def test_minors_cannot_add_children(self):
        self.client.force_login(make_user("teen", age=15))
        self.assertEqual(self.post().status_code, 403)

    def test_invalid_submission_reopens_household(self):
        response = self.post(username="")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "household")
        self.assertFalse(User.objects.filter(first_name="Robin").exists())


class ChildLoginTests(TestCase):
    def setUp(self):
        self.parent = make_user("parent")
        # A child added before logins were universal: placeholder email, no usable password
        self.child = User(
            username="old-kid",
            email=dependent_placeholder_email("old-kid"),
            date_of_birth=born_years_ago(9),
            parent_account=self.parent,
        )
        self.child.set_unusable_password()
        self.child.save()
        self.client.force_login(self.parent)

    def post(self, child, **data):
        prefix = f"child-{child.pk}"
        return self.client.post(
            reverse("accounts:update_child_login", args=[child.pk]),
            {f"{prefix}-{key}": value for key, value in data.items()},
        )

    def test_old_dependent_needs_a_password(self):
        form = ChildLoginForm({"username": "old-kid"}, child=self.child)
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_parent_gives_old_dependent_a_login(self):
        self.post(self.child, username="kiddo", password1=PASSWORD, password2=PASSWORD, email="")
        self.child.refresh_from_db()
        self.assertEqual(self.child.username, "kiddo")
        self.assertEqual(self.child.email, dependent_placeholder_email("kiddo"))
        self.assertTrue(self.client.login(username="kiddo", password=PASSWORD))

    def test_password_can_be_left_blank_to_keep_it(self):
        self.child.set_password(PASSWORD)
        self.child.save()
        self.post(self.child, username="old-kid", password1="", password2="", email="")
        self.assertTrue(self.client.login(username="old-kid", password=PASSWORD))

    def test_adding_an_email_requires_confirming_it(self):
        self.child.set_password(PASSWORD)
        self.child.save()
        self.post(self.child, username="old-kid", password1="", password2="", email="kid@example.test")
        self.child.refresh_from_db()
        self.assertEqual(self.child.email, "kid@example.test")
        self.assertFalse(self.child.is_active)
        self.assertEqual([m.to for m in mail.outbox], [["kid@example.test"]])

    def test_cannot_edit_someone_elses_child(self):
        other = make_user("other", age=10, parent_account=make_user("otherparent"))
        response = self.post(other, username="hijack", password1=PASSWORD, password2=PASSWORD)
        self.assertEqual(response.status_code, 404)


class MinorWaiverTests(TestCase):
    def setUp(self):
        self.waiver = Waiver.objects.create(title="Waiver", content="Terms")
        self.parent = make_user("parent")

    def sign(self, actor, target=None):
        self.client.force_login(actor)
        data = {"waiver_id": self.waiver.id}
        if target is not None:
            data["user_id"] = target.id
        return self.client.post(reverse("accounts:sign_waiver"), data)

    def test_minors_cannot_sign_their_own_waiver(self):
        for teen in (make_user("linked", age=15, parent_account=self.parent), make_user("unlinked", age=15)):
            with self.subTest(teen=teen.username):
                self.sign(teen)
                self.assertFalse(WaiverSignature.objects.filter(user=teen).exists())

    def test_waiver_message_matches_where_the_minor_is_in_linking(self):
        unlinked = make_user("unlinked", age=15)
        self.assertIn(unlinked.email, minor_waiver_message(unlinked))
        unlinked.pending_guardian = self.parent
        self.assertIn("Approve parent's guardian request", minor_waiver_message(unlinked))
        linked = make_user("linked", age=15, parent_account=self.parent)
        self.assertIn("parent needs to sign", minor_waiver_message(linked))
        self.assertIsNone(minor_waiver_message(self.parent))

    def test_parent_signs_for_child(self):
        child = make_user("kid", age=10, parent_account=self.parent)
        self.sign(self.parent, child)
        self.assertTrue(WaiverSignature.objects.filter(user=child, waiver=self.waiver).exists())

    def test_adults_still_sign_their_own(self):
        self.sign(self.parent)
        self.assertTrue(WaiverSignature.objects.filter(user=self.parent).exists())


class HouseholdEmailTests(TestCase):
    def setUp(self):
        self.parent = make_user("parent")

    def test_recipients(self):
        with_email = make_user("withemail", age=15, parent_account=self.parent)
        without_email = make_user(
            "noemail", age=9, parent_account=self.parent, email=dependent_placeholder_email("noemail")
        )
        unlinked = make_user("solo", age=15)
        self.assertEqual(email_recipients(with_email), [self.parent, with_email])
        self.assertEqual(email_recipients(without_email), [self.parent])
        self.assertEqual(email_recipients(unlinked), [unlinked])
        self.assertEqual(email_recipients(self.parent), [self.parent])

    def test_parent_copy_names_the_child(self):
        child = make_user("withemail", first_name="Robin", age=15, parent_account=self.parent)
        send_to_household(child, "New survey", "text", "<p>html</p>")
        subjects = {m.to[0]: m.subject for m in mail.outbox}
        self.assertEqual(subjects[self.parent.email], "For Robin: New survey")
        self.assertEqual(subjects[child.email], "New survey")


class DashboardDeepLinkTests(TestCase):
    def test_open_param_is_whitelisted(self):
        self.client.force_login(make_user("parent"))
        url = reverse("accounts:dashboard")
        self.assertEqual(self.client.get(f"{url}?open=household").context["open_modal"], "household")
        self.assertIsNone(self.client.get(f"{url}?open=');alert(1)//").context["open_modal"])


class UsernameRecoveryTests(TestCase):
    def setUp(self):
        cache.clear()  # Rate-limit counters live in the cache
        self.parent = make_user("parent")
        make_user("robin_h", first_name="Robin", age=10, parent_account=self.parent)

    def recover(self, email):
        return self.client.post(reverse("accounts:username_recovery"), {"email": email})

    def test_login_page_links_to_it(self):
        self.assertContains(self.client.get(reverse("login")), reverse("accounts:username_recovery"))

    def test_sends_username_and_childrens_usernames(self):
        response = self.recover("PARENT@example.test")  # Case-insensitive match
        self.assertRedirects(response, reverse("accounts:username_recovery_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.parent.email])
        self.assertIn("Your username is: parent", mail.outbox[0].body)
        self.assertIn("Robin: robin_h", mail.outbox[0].body)

    def test_unknown_email_looks_the_same_and_sends_nothing(self):
        response = self.recover("nobody@example.test")
        self.assertRedirects(response, reverse("accounts:username_recovery_done"))
        self.assertEqual(mail.outbox, [])

    def test_inactive_accounts_get_nothing(self):
        make_user("pending", is_active=False)
        self.recover("pending@example.test")
        self.assertEqual(mail.outbox, [])
