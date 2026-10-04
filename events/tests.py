from datetime import date, datetime, time, timedelta
from itertools import count

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Waiver
from events.admin import EventRegistrationAdmin
from events.forms import EventRegistrationForm
from events.models import Event, EventPriceTier, EventRegistration, EventType
from events.services.pricing import PromoCodeError, attendee_price, quote_price
from payments.models import PaymentMethod, PaymentStatus, Promotion, Transaction, Voucher

# ==========================================
# FIXTURE HELPERS
# ==========================================

_titles = count(1)


def make_event(event_type=EventType.SENIOR, base_price_cents=6000, days_out=30):
    """
    Two-day event starting 9 AM local on the first Saturday at least `days_out` days away.
    A fixed weekday and start hour keep the early bird / late arrival rules deterministic
    no matter when the tests run.
    """
    day = timezone.localdate() + timedelta(days=days_out)
    day += timedelta(days=(5 - day.weekday()) % 7)
    start = timezone.make_aware(datetime.combine(day, time(hour=9)))
    return Event.objects.create(
        title=f"Test Event {next(_titles)}",
        event_type=event_type,
        base_price_cents=base_price_cents,
        start_time=start,
        end_time=start + timedelta(days=1, hours=8),  # Sunday 5 PM
    )


def born_years_ago(years):
    """A birthday that makes someone `years` old today and for the next few months."""
    today = timezone.localdate()
    return date(today.year - years, today.month, 1) - timedelta(days=200)


def make_user(username, age=36, **extra):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="test-pass",
        date_of_birth=born_years_ago(age),
        **extra,
    )


def make_registration(event, user, final_price_cents=5000, **extra):
    extra.setdefault("base_price_cents", final_price_cents)
    return EventRegistration.objects.create(
        event=event,
        user=user,
        declared_arrival_time=event.start_time,
        final_price_cents=final_price_cents,
        **extra,
    )


def quote(event, user, registration_time=None, arrival_time=None, student=False, rental=False, promo_code=""):
    return quote_price(
        event=event,
        user=user,
        registration_time=registration_time or timezone.now(),
        arrival_time=arrival_time or event.start_time,
        student_discount=student,
        weapon_rental=rental,
        promo_code=promo_code,
    )


def discount_types(q):
    return [d["type"] for d in q.discounts]


# ==========================================
# PRICING: EXISTING RULES
# ==========================================


class AttendeePriceTests(TestCase):
    def setUp(self):
        self.event = make_event(base_price_cents=6000)
        self.user = make_user("adult", age=36)

    def test_no_tiers_uses_base_price(self):
        self.assertEqual(attendee_price(self.event, self.user), 6000)

    def test_matching_tier_price_is_used(self):
        EventPriceTier.objects.create(event=self.event, label="30s", min_age=30, max_age=39, price_cents=4000)
        self.assertEqual(attendee_price(self.event, self.user), 4000)

    def test_age_outside_every_tier_uses_base_price(self):
        EventPriceTier.objects.create(event=self.event, label="Kids", min_age=8, max_age=12, price_cents=2000)
        self.assertEqual(attendee_price(self.event, self.user), 6000)


class FirstTimeDiscountTests(TestCase):
    def setUp(self):
        self.event = make_event(base_price_cents=6000)
        self.newcomer = make_user("newcomer")

    def test_newcomer_gets_free_ticket_and_free_rental(self):
        q = quote(self.event, self.newcomer, rental=True)
        self.assertEqual(discount_types(q), ["first_time"])
        self.assertEqual(
            q.additional_items,
            [{"type": "weapon_rental", "amount_cents": 0, "reason": q.additional_items[0]["reason"]}],
        )
        self.assertEqual(q.final_cents, 0)

    def test_veteran_flag_blocks_discount(self):
        veteran = make_user("vet", is_veteran=True)
        self.assertNotIn("first_time", discount_types(quote(self.event, veteran)))

    def test_checked_in_past_main_event_blocks_discount(self):
        past = make_event(days_out=-60)
        make_registration(past, self.newcomer, checked_in=True)
        self.assertNotIn("first_time", discount_types(quote(self.event, self.newcomer)))

    def test_reservation_at_another_event_blocks_discount(self):
        make_registration(make_event(days_out=90), self.newcomer)
        self.assertNotIn("first_time", discount_types(quote(self.event, self.newcomer)))


class StandardDiscountTests(TestCase):
    def setUp(self):
        self.veteran = make_user("vet", is_veteran=True)

    def test_early_bird_when_registering_more_than_a_week_out(self):
        event = make_event()
        q = quote(event, self.veteran, registration_time=event.start_time - timedelta(days=8))
        self.assertEqual(discount_types(q), ["early_bird"])
        self.assertEqual(q.discounts[0]["amount_cents"], 1000)

    def test_no_early_bird_after_cutoff(self):
        event = make_event()
        q = quote(event, self.veteran, registration_time=event.start_time - timedelta(days=3))
        self.assertEqual(q.discounts, [])
        self.assertEqual(q.final_cents, 6000)

    def test_weapon_rental_is_charged(self):
        event = make_event()
        q = quote(event, self.veteran, registration_time=event.start_time - timedelta(days=3), rental=True)
        self.assertEqual(q.additional_items[0]["amount_cents"], 2000)
        self.assertEqual(q.final_cents, 8000)

    def assert_late_arrival(self, event_type, arrival_offset, expected_type, expected_cents):
        event = make_event(event_type=event_type)
        q = quote(
            event,
            self.veteran,
            registration_time=event.start_time - timedelta(days=3),  # skip early bird
            arrival_time=event.start_time + arrival_offset,
        )
        if expected_type is None:
            self.assertEqual(q.discounts, [])
        else:
            self.assertEqual(q.discounts, [{**q.discounts[0], "type": expected_type, "amount_cents": expected_cents}])

    def test_junior_late_arrivals(self):
        # Start is Saturday 9 AM: +6h = Saturday 3 PM, +1 day = Sunday, +5h = Saturday 2 PM
        self.assert_late_arrival(EventType.JUNIOR, timedelta(hours=6), "late_arrival_saturday", 1000)
        self.assert_late_arrival(EventType.JUNIOR, timedelta(days=1), "late_arrival_sunday", 2000)
        self.assert_late_arrival(EventType.JUNIOR, timedelta(hours=5), None, 0)

    def test_senior_late_arrivals(self):
        self.assert_late_arrival(EventType.SENIOR, timedelta(hours=6), "late_arrival_saturday", 500)
        self.assert_late_arrival(EventType.SENIOR, timedelta(days=1), "late_arrival_sunday", 1500)
        self.assert_late_arrival(EventType.SENIOR, timedelta(hours=5), None, 0)

    def test_student_discount_senior_only(self):
        senior = make_event(event_type=EventType.SENIOR)
        junior = make_event(event_type=EventType.JUNIOR)
        late_reg = senior.start_time - timedelta(days=3)

        self.assertEqual(
            discount_types(quote(senior, self.veteran, registration_time=late_reg, student=True)), ["student_discount"]
        )
        self.assertEqual(quote(junior, self.veteran, registration_time=late_reg, student=True).discounts, [])

    def test_discounts_clamp_ticket_to_zero_but_not_add_ons(self):
        # $20 ticket with $10 early bird + $15 Sunday arrival + $5 student = $30 of discounts
        event = make_event(base_price_cents=2000)
        q = quote(event, self.veteran, arrival_time=event.start_time + timedelta(days=1), student=True, rental=True)
        self.assertEqual(sum(d["amount_cents"] for d in q.discounts), 3000)
        self.assertEqual(q.final_cents, 2000)  # ticket $0 + $20 rental


# ==========================================
# PRICING: PROMO CODES
# ==========================================


class PromoCodePricingTests(TestCase):
    def setUp(self):
        # $60 senior event a month out: registering now earns only the $10 early bird discount
        self.event = make_event(base_price_cents=6000)
        self.veteran = make_user("veteran", is_veteran=True)
        self.newcomer = make_user("newcomer")

    def test_voucher_is_the_only_discount_and_rental_still_charged(self):
        voucher = Voucher.objects.create()
        q = quote(self.event, self.veteran, promo_code=voucher.code, rental=True)

        self.assertEqual(len(q.discounts), 1)
        self.assertEqual(q.discounts[0]["type"], "voucher")
        self.assertEqual(q.discounts[0]["amount_cents"], 6000)
        self.assertEqual(q.final_cents, 2000)
        self.assertEqual(q.voucher_id, voucher.id)

    def test_used_voucher_is_rejected(self):
        voucher = Voucher.objects.create(used_at=timezone.now())
        with self.assertRaisesMessage(PromoCodeError, "already been used"):
            quote(self.event, self.veteran, promo_code=voucher.code)

    def test_percent_promotion_applies_after_flat_discounts(self):
        Promotion.objects.create(code="TENOFF", name="Ten Percent", percent_off=10)
        q = quote(self.event, self.veteran, promo_code="TENOFF")

        # $60 - $10 early bird = $50, then 10% off = $45
        self.assertEqual(discount_types(q), ["early_bird", "promotion"])
        self.assertEqual(q.discounts[1]["amount_cents"], 500)
        self.assertEqual(q.final_cents, 4500)
        self.assertIsNone(q.voucher_id)

    def test_flat_promotion_clamps_to_zero(self):
        Promotion.objects.create(
            code="BIGFLAT", name="Big", discount_type=Promotion.DiscountType.FLAT, amount_off_cents=10000
        )
        q = quote(self.event, self.veteran, promo_code="BIGFLAT")

        self.assertEqual(q.discounts[-1]["amount_cents"], 5000)
        self.assertEqual(q.final_cents, 0)

    def test_unusable_promotions_are_rejected(self):
        now = timezone.now()
        Promotion.objects.create(
            code="EXPIRED",
            name="x",
            percent_off=10,
            starts_at=now - timedelta(days=5),
            expires_at=now - timedelta(days=1),
        )
        Promotion.objects.create(code="INACTIVE", name="x", percent_off=10, is_active=False)
        Promotion.objects.create(code="FUTURE", name="x", percent_off=10, starts_at=now + timedelta(days=1))

        for code in ["EXPIRED", "INACTIVE", "FUTURE", "NOSUCHCODE"]:
            with self.subTest(code=code), self.assertRaisesMessage(PromoCodeError, "No promotions were found"):
                quote(self.event, self.veteran, promo_code=code)

    def test_codes_are_case_insensitive(self):
        Promotion.objects.create(code="anniversary10", name="Anniversary", percent_off=10)
        q = quote(self.event, self.veteran, promo_code="  Anniversary10 ")
        self.assertEqual(q.discounts[-1]["type"], "promotion")

    def test_first_timer_voucher_rejected_and_not_used(self):
        voucher = Voucher.objects.create()
        with self.assertRaisesMessage(PromoCodeError, "already free"):
            quote(self.event, self.newcomer, promo_code=voucher.code)

        voucher.refresh_from_db()
        self.assertFalse(voucher.is_used)

    def test_no_code_leaves_pricing_unchanged(self):
        q = quote(self.event, self.veteran)
        self.assertEqual(q.final_cents, 5000)
        self.assertIsNone(q.voucher_id)


class VoucherModelTests(TestCase):
    def test_blank_code_is_generated(self):
        first, second = Voucher.objects.create(), Voucher.objects.create()

        self.assertEqual(len(first.code), 10)
        self.assertEqual(first.code, first.code.upper())
        self.assertNotEqual(first.code, second.code)


# ==========================================
# REGISTRATION MODEL: RETROACTIVE PRICE CHANGES
# ==========================================


class RegistrationPriceAdjustmentTests(TestCase):
    def setUp(self):
        self.event = make_event()
        self.user = make_user("vet", is_veteran=True)
        # $60 base - $10 early bird + $20 rental = $70
        self.registration = make_registration(
            self.event,
            self.user,
            base_price_cents=6000,
            final_price_cents=7000,
            discounts=[{"type": "early_bird", "amount_cents": 1000, "reason": "Early Bird"}],
            additional_items=[{"type": "weapon_rental", "amount_cents": 2000, "reason": "Weapon Rental"}],
        )

    def test_unedited_registration_has_no_adjustment(self):
        self.assertEqual(self.registration.price_adjustment_cents, 0)
        self.assertIsNone(self.registration.formatted_price_adjustment)

    def test_lowered_price_is_a_credit(self):
        self.registration.final_price_cents = 5500
        self.assertEqual(self.registration.formatted_price_adjustment, {"amount": 15.0, "is_credit": True})

    def test_raised_price_is_a_charge(self):
        self.registration.final_price_cents = 7500
        self.assertEqual(self.registration.formatted_price_adjustment, {"amount": 5.0, "is_credit": False})

    def test_clamped_breakdown_has_no_adjustment(self):
        # Discounts larger than the ticket are clamped to $0, so only the rental is owed
        self.registration.discounts = [{"type": "voucher", "amount_cents": 9000, "reason": "Big"}]
        self.registration.final_price_cents = 2000
        self.assertEqual(self.registration.price_adjustment_cents, 0)


class ZeroDollarSettlementTests(TestCase):
    def setUp(self):
        self.event = make_event()
        self.user = make_user("vet", is_veteran=True)

    def test_lowering_price_to_zero_settles_registration(self):
        registration = make_registration(self.event, self.user, final_price_cents=5000)
        self.assertFalse(registration.is_paid)

        registration.final_price_cents = 0
        registration.save()

        registration.refresh_from_db()
        self.assertTrue(registration.is_paid)
        self.assertEqual(registration.transaction.total_amount_cents, 0)

    def test_zero_dollar_replaces_incomplete_checkout_transaction(self):
        pending = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.INCOMPLETE)
        registration = make_registration(self.event, self.user, final_price_cents=5000, transaction=pending)

        registration.final_price_cents = 0
        registration.save()

        self.assertTrue(registration.is_paid)
        self.assertNotEqual(registration.transaction_id, pending.id)

    def test_paid_registration_is_not_settled_twice(self):
        paid = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.SUCCEEDED)
        registration = make_registration(self.event, self.user, final_price_cents=5000, transaction=paid)

        registration.final_price_cents = 0
        registration.save()

        self.assertEqual(registration.transaction_id, paid.id)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_refunded_registration_is_left_alone(self):
        refunded = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.REFUNDED)
        registration = make_registration(self.event, self.user, final_price_cents=5000, transaction=refunded)

        registration.final_price_cents = 0
        registration.save()

        self.assertEqual(registration.transaction_id, refunded.id)

    def test_gate_payment_on_paid_registration_does_not_duplicate(self):
        paid = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.SUCCEEDED)
        registration = make_registration(self.event, self.user, final_price_cents=5000, transaction=paid)

        registration.checked_in = True
        registration.in_person_payment_received = True
        registration.save()

        self.assertEqual(registration.transaction_id, paid.id)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_gate_payment_on_unpaid_registration_records_in_person_payment(self):
        registration = make_registration(self.event, self.user, final_price_cents=5000)

        registration.checked_in = True
        registration.in_person_payment_received = True
        registration.save()

        self.assertTrue(registration.is_paid)
        self.assertEqual(registration.transaction.payment_method, PaymentMethod.IN_PERSON)
        self.assertEqual(registration.transaction.total_amount_cents, 5000)


class RegistrationAdminTests(TestCase):
    def setUp(self):
        self.model_admin = EventRegistrationAdmin(EventRegistration, admin.site)
        self.request = RequestFactory().get("/")
        self.event = make_event()
        self.user = make_user("vet", is_veteran=True)

    def test_final_price_editable_while_unpaid(self):
        registration = make_registration(self.event, self.user)
        self.assertNotIn("final_price_cents", self.model_admin.get_readonly_fields(self.request, registration))

    def test_final_price_locked_once_paid(self):
        paid = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.SUCCEEDED)
        registration = make_registration(self.event, self.user, transaction=paid)
        self.assertIn("final_price_cents", self.model_admin.get_readonly_fields(self.request, registration))


# ==========================================
# REGISTRATION FORM
# ==========================================


def form_data(event, day_offset=0, hour="9", minute="00", period="AM", payment_method="in_person", **extra):
    arrival_day = timezone.localtime(event.start_time).date() + timedelta(days=day_offset)
    return {
        "arrival_date": arrival_day.isoformat(),
        "arrival_hour": hour,
        "arrival_minute": minute,
        "arrival_period": period,
        "payment_method": payment_method,
        **extra,
    }


class EventRegistrationFormTests(TestCase):
    def setUp(self):
        self.event = make_event()
        self.veteran = make_user("vet", is_veteran=True)
        self.newcomer = make_user("newcomer")

    def test_arrival_date_choices_cover_every_event_day(self):
        form = EventRegistrationForm(event=self.event, user=self.veteran)
        start = timezone.localtime(self.event.start_time).date()
        self.assertEqual(
            [value for value, _ in form.fields["arrival_date"].choices],
            [start.isoformat(), (start + timedelta(days=1)).isoformat()],
        )

    def test_valid_arrival_is_combined(self):
        form = EventRegistrationForm(form_data(self.event, hour="3", period="PM"), event=self.event, user=self.veteran)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["declared_arrival_time"], self.event.start_time + timedelta(hours=6))

    def test_arrival_before_start_is_rejected(self):
        form = EventRegistrationForm(form_data(self.event, hour="8"), event=self.event, user=self.veteran)
        self.assertIn("before the event", form.errors["arrival_date"][0])

    def test_arrival_after_end_is_rejected(self):
        data = form_data(self.event, day_offset=1, hour="11", period="PM")
        form = EventRegistrationForm(data, event=self.event, user=self.veteran)
        self.assertIn("after the event", form.errors["arrival_date"][0])

    def test_date_without_time_parts_is_rejected(self):
        data = form_data(self.event, hour="")
        form = EventRegistrationForm(data, event=self.event, user=self.veteran)
        self.assertIn("Please choose an hour", form.errors["arrival_date"][0])

    def test_first_event_question_hidden_for_veterans(self):
        self.assertNotIn("is_first_event", EventRegistrationForm(event=self.event, user=self.veteran).fields)
        self.assertIn("is_first_event", EventRegistrationForm(event=self.event, user=self.newcomer).fields)

    def test_first_event_question_is_required_with_no_default(self):
        unbound = EventRegistrationForm(event=self.event, user=self.newcomer)
        self.assertIsNone(unbound["is_first_event"].value())

        form = EventRegistrationForm(form_data(self.event), event=self.event, user=self.newcomer)
        self.assertIn("is_first_event", form.errors)

    def test_first_event_answers_clean_to_booleans(self):
        for answer, expected in [("True", True), ("False", False)]:
            with self.subTest(answer=answer):
                data = form_data(self.event, is_first_event=answer)
                form = EventRegistrationForm(data, event=self.event, user=self.newcomer)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertIs(form.cleaned_data["is_first_event"], expected)


# ==========================================
# REGISTRATION VIEW
# ==========================================


class EventRegistrationViewTests(TestCase):
    def setUp(self):
        self.senior = make_event(event_type=EventType.SENIOR, base_price_cents=6000)
        self.junior = make_event(event_type=EventType.JUNIOR, base_price_cents=4000)
        self.veteran = make_user("vet", is_veteran=True)

    def url(self, event, user_id=None):
        if user_id:
            return reverse("events:register_sub", kwargs={"slug": event.slug, "user_id": user_id})
        return reverse("events:register", kwargs={"slug": event.slug})

    def post_as(self, user, event, user_id=None, **data):
        self.client.force_login(user)
        return self.client.post(self.url(event, user_id), form_data(event, **data))

    def make_child(self, username, age):
        return make_user(username, age=age, parent_account=self.veteran)

    def test_age_gates(self):
        cases = [
            (self.make_child("tooyoung", 7), self.junior),
            (self.veteran, self.junior),  # adults can't attend junior events
            (self.make_child("teen", 15), self.senior),
        ]
        for user, event in cases:
            with self.subTest(user=user.username, event=event.event_type):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url(event)).status_code, 403)

    def test_minor_without_guardian_is_redirected(self):
        self.client.force_login(make_user("orphan", age=15))
        response = self.client.get(self.url(self.junior))
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_unsigned_active_waiver_is_redirected(self):
        Waiver.objects.create(title="Waiver", content="Terms")
        self.client.force_login(self.veteran)
        response = self.client.get(self.url(self.senior))
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_duplicate_registration_is_blocked(self):
        make_registration(self.senior, self.veteran)
        response = self.post_as(self.veteran, self.senior)
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        self.assertEqual(EventRegistration.objects.filter(user=self.veteran).count(), 1)

    def test_in_person_registration_is_saved_with_quoted_price(self):
        response = self.post_as(self.veteran, self.senior, weapon_rental="on")
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)

        registration = EventRegistration.objects.get(user=self.veteran, event=self.senior)
        # $60 - $10 early bird + $20 rental
        self.assertEqual(registration.final_price_cents, 7000)
        self.assertFalse(registration.is_paid)

    def test_online_registration_goes_to_checkout(self):
        response = self.post_as(self.veteran, self.senior, payment_method="online")
        self.assertRedirects(response, reverse("payments:checkout"), fetch_redirect_response=False)

    def test_first_timer_registration_is_free_and_paid(self):
        newcomer = make_user("newcomer")
        self.post_as(newcomer, self.senior, is_first_event="True")

        newcomer.refresh_from_db()
        registration = EventRegistration.objects.get(user=newcomer)
        self.assertEqual(registration.final_price_cents, 0)
        self.assertTrue(registration.is_paid)
        self.assertFalse(newcomer.is_veteran)

    def test_answering_not_first_event_marks_veteran(self):
        newcomer = make_user("returning")
        self.post_as(newcomer, self.senior, is_first_event="False")

        newcomer.refresh_from_db()
        self.assertTrue(newcomer.is_veteran)
        self.assertGreater(EventRegistration.objects.get(user=newcomer).final_price_cents, 0)

    def test_skipping_first_event_question_saves_nothing(self):
        newcomer = make_user("undecided")
        response = self.post_as(newcomer, self.senior)

        newcomer.refresh_from_db()
        self.assertContains(response, "Please let us know whether this is your first Claritas event.")
        self.assertFalse(newcomer.is_veteran)
        self.assertFalse(EventRegistration.objects.filter(user=newcomer).exists())

    def test_age_gate_uses_local_event_date(self):
        # Saturday 8 PM Central is already Sunday in UTC. A player whose 18th birthday is that Sunday
        # is still 17 on the local event date, so the senior event must turn them away.
        evening = make_event(event_type=EventType.SENIOR)
        evening.start_time += timedelta(hours=11)  # 9 AM -> 8 PM local
        evening.save()
        evening.refresh_from_db()  # times come back from the database in UTC, as the view sees them
        sunday = timezone.localdate(evening.start_time) + timedelta(days=1)
        self.assertEqual(evening.start_time.date(), sunday)  # sanity check: the UTC date is Sunday

        almost_adult = make_user("almost18", parent_account=self.veteran)
        almost_adult.date_of_birth = date(sunday.year - 18, sunday.month, sunday.day)
        almost_adult.save()

        self.client.force_login(almost_adult)
        self.assertEqual(self.client.get(self.url(evening)).status_code, 403)

    def test_parent_registers_child(self):
        child = self.make_child("kid", 12)
        self.post_as(self.veteran, self.junior, user_id=child.id, is_first_event="True")
        self.assertTrue(EventRegistration.objects.filter(user=child, event=self.junior).exists())

    def test_cannot_register_someone_elses_child(self):
        other_parent = make_user("otherparent")
        child = make_user("otherkid", age=12, parent_account=other_parent)
        self.client.force_login(self.veteran)
        self.assertEqual(self.client.get(self.url(self.junior, child.id)).status_code, 404)

    def test_bad_promo_code_saves_nothing(self):
        response = self.post_as(self.veteran, self.senior, promo_code="NOPE")
        self.assertEqual(response.status_code, 200)
        # Shown once, under the promo field, with no duplicate banner at the top of the page
        self.assertContains(response, "No promotions were found", count=1)
        self.assertEqual(list(response.context["messages"]), [])
        self.assertFalse(EventRegistration.objects.filter(user=self.veteran).exists())

    def test_voucher_registration_redeems_voucher(self):
        voucher = Voucher.objects.create()
        self.post_as(self.veteran, self.senior, promo_code=voucher.code.lower())

        registration = EventRegistration.objects.get(user=self.veteran)
        voucher.refresh_from_db()
        self.assertTrue(registration.is_paid)
        self.assertEqual(voucher.used_by_registration, registration)
