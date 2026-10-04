from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventType
from events.services.pricing import PromoCodeError, quote_price
from payments.models import Promotion, Voucher


class PromoCodePricingTests(TestCase):
    def setUp(self):
        # Senior event a month out at $60 starting 9 AM (before the late-arrival cutoff),
        # so registering now earns only the $10 early bird discount
        start = timezone.localtime() + timedelta(days=30)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
        self.event = Event.objects.create(
            title="Promo Test",
            event_type=EventType.SENIOR,
            base_price_cents=6000,
            start_time=start,
            end_time=start + timedelta(days=1),
        )
        # Veterans skip the first-time discount, so the normal pricing rules apply
        self.veteran = get_user_model().objects.create_user(
            username="veteran", email="vet@example.com", password="x", date_of_birth=date(1990, 1, 1), is_veteran=True
        )
        self.newcomer = get_user_model().objects.create_user(
            username="newcomer", email="new@example.com", password="x", date_of_birth=date(1990, 1, 1)
        )

    def quote(self, user=None, promo_code="", weapon_rental=False):
        return quote_price(
            event=self.event,
            user=user or self.veteran,
            registration_time=timezone.now(),
            arrival_time=self.event.start_time,
            student_discount=False,
            weapon_rental=weapon_rental,
            promo_code=promo_code,
        )

    def test_voucher_is_the_only_discount_and_rental_still_charged(self):
        voucher = Voucher.objects.create()
        quote = self.quote(promo_code=voucher.code, weapon_rental=True)

        self.assertEqual(len(quote.discounts), 1)
        self.assertEqual(quote.discounts[0]["type"], "voucher")
        self.assertEqual(quote.discounts[0]["amount_cents"], 6000)
        self.assertEqual(quote.final_cents, 2000)
        self.assertEqual(quote.voucher_id, voucher.id)

    def test_used_voucher_is_rejected(self):
        voucher = Voucher.objects.create(used_at=timezone.now())
        with self.assertRaisesMessage(PromoCodeError, "already been used"):
            self.quote(promo_code=voucher.code)

    def test_percent_promotion_applies_after_flat_discounts(self):
        Promotion.objects.create(code="TENOFF", name="Ten Percent", percent_off=10)
        quote = self.quote(promo_code="TENOFF")

        # $60 - $10 early bird = $50, then 10% off = $45
        self.assertEqual([d["type"] for d in quote.discounts], ["early_bird", "promotion"])
        self.assertEqual(quote.discounts[1]["amount_cents"], 500)
        self.assertEqual(quote.final_cents, 4500)
        self.assertIsNone(quote.voucher_id)

    def test_flat_promotion_clamps_to_zero(self):
        Promotion.objects.create(
            code="BIGFLAT", name="Big", discount_type=Promotion.DiscountType.FLAT, amount_off_cents=10000
        )
        quote = self.quote(promo_code="BIGFLAT")

        self.assertEqual(quote.discounts[-1]["amount_cents"], 5000)
        self.assertEqual(quote.final_cents, 0)

    def test_unusable_promotions_are_rejected(self):
        now = timezone.now()
        Promotion.objects.create(
            code="EXPIRED",
            name="x",
            percent_off=10,
            expires_at=now - timedelta(days=1),
            starts_at=now - timedelta(days=5),
        )
        Promotion.objects.create(code="INACTIVE", name="x", percent_off=10, is_active=False)
        Promotion.objects.create(code="FUTURE", name="x", percent_off=10, starts_at=now + timedelta(days=1))

        for code in ["EXPIRED", "INACTIVE", "FUTURE", "NOSUCHCODE"]:
            with self.subTest(code=code), self.assertRaisesMessage(PromoCodeError, "No promotions were found"):
                self.quote(promo_code=code)

    def test_codes_are_case_insensitive(self):
        Promotion.objects.create(code="anniversary10", name="Anniversary", percent_off=10)
        quote = self.quote(promo_code="  Anniversary10 ")
        self.assertEqual(quote.discounts[-1]["type"], "promotion")

    def test_first_timer_voucher_rejected_and_not_used(self):
        voucher = Voucher.objects.create()
        with self.assertRaisesMessage(PromoCodeError, "already free"):
            self.quote(user=self.newcomer, promo_code=voucher.code)

        voucher.refresh_from_db()
        self.assertFalse(voucher.is_used)

    def test_no_code_leaves_pricing_unchanged(self):
        quote = self.quote()
        self.assertEqual(quote.final_cents, 5000)
        self.assertIsNone(quote.voucher_id)


class VoucherModelTests(TestCase):
    def test_blank_code_is_generated(self):
        first, second = Voucher.objects.create(), Voucher.objects.create()

        self.assertEqual(len(first.code), 10)
        self.assertEqual(first.code, first.code.upper())
        self.assertNotEqual(first.code, second.code)
