from unittest import mock

import stripe
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from events.models import EventRegistration
from events.tests import make_event, make_registration, make_user
from payments.models import PaymentStatus, Transaction
from payments.services import get_outstanding_registrations, record_refund


class OutstandingRegistrationsTests(TestCase):
    def setUp(self):
        self.event = make_event()
        self.user = make_user("vet", is_veteran=True)

    def test_unpaid_registration_is_outstanding(self):
        registration = make_registration(self.event, self.user, final_price_cents=5000)
        self.assertEqual(list(get_outstanding_registrations([self.user.id])), [registration])

    def test_unsettled_zero_dollar_registration_is_not_outstanding(self):
        # Simulate a $0 row left over from before registrations settled themselves
        registration = make_registration(self.event, self.user, final_price_cents=5000)
        EventRegistration.objects.filter(pk=registration.pk).update(final_price_cents=0)
        self.assertFalse(get_outstanding_registrations([self.user.id]).exists())

    def test_finished_event_without_check_in_is_not_outstanding(self):
        make_registration(make_event(days_out=-60), self.user, final_price_cents=5000)
        self.assertFalse(get_outstanding_registrations([self.user.id]).exists())


@mock.patch("payments.views.stripe.PaymentIntent")
class CheckoutPageTests(TestCase):
    def setUp(self):
        self.event = make_event()
        self.user = make_user("vet", is_veteran=True)
        self.client.force_login(self.user)
        self.dashboard = reverse("accounts:dashboard")

    def checkout(self):
        return self.client.get(reverse("payments:checkout"))

    def test_nothing_owed_redirects_without_stripe(self, payment_intent):
        make_registration(self.event, self.user, final_price_cents=0)
        self.assertRedirects(self.checkout(), self.dashboard, fetch_redirect_response=False)
        payment_intent.create.assert_not_called()

    def test_balance_below_stripe_minimum_redirects_without_stripe(self, payment_intent):
        make_registration(self.event, self.user, final_price_cents=30)
        response = self.checkout()
        self.assertRedirects(response, self.dashboard, fetch_redirect_response=False)
        payment_intent.create.assert_not_called()

    def test_stripe_failure_redirects_with_message(self, payment_intent):
        payment_intent.create.side_effect = Exception("Stripe is down")
        make_registration(self.event, self.user, final_price_cents=5000)

        with self.assertLogs("payments.views", level="ERROR"):
            response = self.client.get(reverse("payments:checkout"), follow=False)

        self.assertRedirects(response, self.dashboard, fetch_redirect_response=False)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertIn("couldn't start your online payment", messages[0])

    def pending_checkout(self, final_price_cents=5000, intent_id="pi_old"):
        """A registration already sitting on an unpaid checkout from an earlier visit."""
        old = Transaction.objects.create(
            total_amount_cents=5000, payment_status=PaymentStatus.INCOMPLETE, stripe_session_id=intent_id
        )
        registration = make_registration(self.event, self.user, final_price_cents=final_price_cents, transaction=old)
        return registration, old

    def test_unchanged_balance_reuses_existing_payment(self, payment_intent):
        payment_intent.retrieve.return_value = mock.Mock(id="pi_old", client_secret="secret")
        registration, old = self.pending_checkout()

        self.assertEqual(self.checkout().status_code, 200)
        payment_intent.create.assert_not_called()
        payment_intent.cancel.assert_not_called()
        registration.refresh_from_db()
        self.assertEqual(registration.transaction_id, old.id)

    def test_changed_balance_cancels_old_payment_before_replacing_it(self, payment_intent):
        payment_intent.create.return_value = mock.Mock(id="pi_new", client_secret="secret")
        registration, old = self.pending_checkout(final_price_cents=3000)  # staff lowered $50 -> $30

        self.assertEqual(self.checkout().status_code, 200)

        payment_intent.cancel.assert_called_once_with("pi_old")
        self.assertEqual(payment_intent.create.call_args.kwargs["amount"], 3000)
        old.refresh_from_db()
        registration.refresh_from_db()
        self.assertEqual(old.payment_status, PaymentStatus.CANCELED)
        self.assertEqual(registration.transaction.stripe_session_id, "pi_new")

    def test_old_payment_already_paid_is_not_replaced(self, payment_intent):
        payment_intent.cancel.side_effect = stripe.InvalidRequestError("Cannot cancel a succeeded intent", None)
        payment_intent.retrieve.return_value = mock.Mock(status="succeeded")
        registration, old = self.pending_checkout(final_price_cents=3000)

        response = self.checkout()

        self.assertRedirects(response, self.dashboard, fetch_redirect_response=False)
        payment_intent.create.assert_not_called()
        registration.refresh_from_db()
        self.assertEqual(registration.transaction_id, old.id)  # still attached, so the webhook marks it paid

    def test_same_total_with_different_registrations_is_not_reused(self, payment_intent):
        # Old $50 checkout covered one registration; it was lowered to $30 and a new $20 one was added.
        payment_intent.create.return_value = mock.Mock(id="pi_new", client_secret="secret")
        lowered, old = self.pending_checkout(final_price_cents=3000)
        added = make_registration(make_event(days_out=60), self.user, final_price_cents=2000)

        self.assertEqual(self.checkout().status_code, 200)

        payment_intent.cancel.assert_called_once_with("pi_old")
        for registration in (lowered, added):
            registration.refresh_from_db()
            self.assertEqual(registration.transaction.stripe_session_id, "pi_new")

    def test_canceled_payment_stays_outstanding(self, payment_intent):
        canceled = Transaction.objects.create(total_amount_cents=5000, payment_status=PaymentStatus.CANCELED)
        make_registration(self.event, self.user, final_price_cents=5000, transaction=canceled)
        self.assertTrue(get_outstanding_registrations([self.user.id]).exists())

    def test_balance_creates_payment_intent_for_total(self, payment_intent):
        payment_intent.create.return_value = mock.Mock(id="pi_test", client_secret="secret")
        make_registration(self.event, self.user, final_price_cents=5000)

        response = self.checkout()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment_intent.create.call_args.kwargs["amount"], 5000)
        registration = EventRegistration.objects.get(user=self.user)
        self.assertEqual(registration.transaction.stripe_session_id, "pi_test")


class RefundTests(TestCase):
    def setUp(self):
        self.parent = make_user("parent", is_veteran=True)
        self.kid = make_user("kid", age=12, parent_account=self.parent, is_veteran=True)
        self.event = make_event()

    def paid(self, *registrations_cents, intent_id="pi_paid"):
        """One succeeded payment covering a registration per price given (parent first, then kid)."""
        txn = Transaction.objects.create(
            total_amount_cents=sum(registrations_cents),
            payment_status=PaymentStatus.SUCCEEDED,
            stripe_session_id=intent_id,
        )
        users = [self.parent, self.kid]
        regs = [
            make_registration(self.event, users[i], final_price_cents=cents, transaction=txn)
            for i, cents in enumerate(registrations_cents)
        ]
        return txn, regs

    def refresh(self, *objs):
        for obj in objs:
            obj.refresh_from_db()

    def test_full_refund_marks_every_registration(self):
        txn, (a, b) = self.paid(5000, 3000)
        record_refund(txn, 8000)
        self.refresh(txn, a, b)

        self.assertEqual(txn.payment_status, PaymentStatus.REFUNDED)
        self.assertEqual((a.refunded_cents, b.refunded_cents), (5000, 3000))
        self.assertTrue(a.is_refunded and b.is_refunded)
        self.assertIsNotNone(a.refunded_at)

    def test_partial_refund_on_single_registration_is_assigned(self):
        txn, (a,) = self.paid(5000)
        record_refund(txn, 1000)
        self.refresh(txn, a)

        self.assertEqual(txn.payment_status, PaymentStatus.SUCCEEDED)  # still paid
        self.assertEqual(a.refunded_cents, 1000)
        self.assertTrue(a.is_partially_refunded)
        self.assertTrue(a.is_paid)

    def test_partial_refund_on_household_payment_waits_for_admin(self):
        txn, (a, b) = self.paid(5000, 3000)
        with self.assertLogs("payments.services", level="WARNING"):
            record_refund(txn, 3000)
        self.refresh(txn, a, b)

        self.assertEqual(txn.refunded_amount_cents, 3000)
        self.assertEqual((a.refunded_cents, b.refunded_cents), (0, 0))
        self.assertEqual(txn.unallocated_refund_cents, 3000)

        # Staff assign it to the kid in admin; nothing is left unassigned
        b.refunded_cents = 3000
        b.save()
        self.assertEqual(txn.unallocated_refund_cents, 0)
        self.assertTrue(b.is_refunded)
        self.assertFalse(a.is_refunded or a.is_partially_refunded)

    def test_refund_larger_than_payment_is_capped(self):
        txn, (a,) = self.paid(5000)
        record_refund(txn, 9999)
        self.refresh(txn, a)
        self.assertEqual((txn.refunded_amount_cents, a.refunded_cents), (5000, 5000))

    def test_registration_refund_cannot_exceed_price(self):
        _, (a,) = self.paid(5000)
        a.refunded_cents = 6000
        with self.assertRaises(ValidationError):
            a.full_clean()

    @mock.patch("payments.views.stripe.Webhook.construct_event")
    def test_webhook_records_partial_refund(self, construct_event):
        txn, (a,) = self.paid(5000)
        construct_event.return_value = {
            "type": "charge.refunded",
            "data": {"object": {"payment_intent": "pi_paid", "amount_refunded": 2000}},
        }

        response = self.client.post(reverse("payments:stripe_webhook"), data=b"{}", content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.refresh(txn, a)
        self.assertEqual(txn.payment_status, PaymentStatus.SUCCEEDED)
        self.assertEqual(a.refunded_cents, 2000)

    def test_admin_force_refund_records_full_refund(self):
        from django.contrib import admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from payments.admin import TransactionAdmin

        txn, (a, b) = self.paid(5000, 3000)
        request = RequestFactory().post("/")
        request.session = {}
        request._messages = FallbackStorage(request)

        TransactionAdmin(Transaction, admin.site).force_mark_refunded(request, Transaction.objects.filter(pk=txn.pk))

        self.refresh(txn, a, b)
        self.assertEqual(txn.payment_status, PaymentStatus.REFUNDED)
        self.assertTrue(a.is_refunded and b.is_refunded)

    def test_dashboard_payment_history_shows_refunds(self):
        txn, (a, b) = self.paid(5000, 3000)
        b.refunded_cents = 3000
        b.save()
        Transaction.objects.create(total_amount_cents=1000, payment_status=PaymentStatus.INCOMPLETE)  # not shown

        self.client.force_login(self.parent)
        response = self.client.get(reverse("accounts:dashboard"))

        self.assertEqual(list(response.context["payment_history"]), [txn])
        self.assertContains(response, "Payment History")
        self.assertContains(response, "-$30.00")
        self.assertContains(response, "Partially Refunded", count=0)
        self.assertContains(response, ">Refunded</span>")  # kid's schedule badge
