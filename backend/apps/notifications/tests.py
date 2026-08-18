from decimal import Decimal
from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.account.models import User
from apps.shops.models import Customer, Shop
from apps.ledger.models import Payment, UdharoEntry, UdharoEntryItem
from apps.ledger.tasks.services import calculate_credit_score

from .models import Notification
from .tasks import send_daily_digests


def make_user_with_shop(email="owner@example.com"):
    user = User.objects.create_user(email=email, password="Str0ngPass!23")
    shop = Shop.objects.create(owner=user, name=f"{email}'s shop")
    return user, shop


class NotificationSignalTests(TestCase):
    """Signals fire no matter how the row gets created (see signals.py's own
    docstring) — these go straight at the model layer, not the API, to
    confirm that."""

    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")

    def test_creating_customer_notifies(self):
        # Customer created in setUp already fired this once.
        notif = Notification.objects.get(
            shop=self.shop, notif_type=Notification.NotifType.CUSTOMER_ADDED
        )
        self.assertEqual(notif.customer, self.customer)
        self.assertFalse(notif.is_read)

    def test_payment_received_notifies(self):
        Payment.objects.create(customer=self.customer, amount_paid=Decimal("100"))

        self.assertTrue(
            Notification.objects.filter(
                shop=self.shop, notif_type=Notification.NotifType.PAYMENT_RECEIVED
            ).exists()
        )

    def test_udharo_entry_notifies_only_after_commit(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )

        # TestCase wraps each test in a transaction that's rolled back, not
        # committed, so on_commit callbacks don't run until explicitly
        # captured — this is what stops a notification firing for an entry
        # whose creating request ultimately fails/rolls back.
        self.assertFalse(
            Notification.objects.filter(
                shop=self.shop, notif_type=Notification.NotifType.UDHARO_CREATED
            ).exists()
        )

    def test_udharo_entry_notifies_with_correct_total_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            entry = UdharoEntry.objects.create(customer=self.customer)
            UdharoEntryItem.objects.create(
                entry=entry, item_name="Rice", amount=Decimal("500")
            )

        notif = Notification.objects.get(
            shop=self.shop, notif_type=Notification.NotifType.UDHARO_CREATED
        )
        self.assertIn("500", notif.message)

    def test_credit_risk_red_notifies_only_on_transition(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        UdharoEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        for _ in range(3):
            Payment.objects.create(customer=self.customer, amount_paid=Decimal("10"))

        score = calculate_credit_score(self.customer)  # -> red (see ledger tests)
        self.assertEqual(score, 20)
        self.assertEqual(
            Notification.objects.filter(
                shop=self.shop, notif_type=Notification.NotifType.CREDIT_RISK_RED
            ).count(),
            1,
        )

        calculate_credit_score(self.customer)  # still red, second time in a row

        self.assertEqual(
            Notification.objects.filter(
                shop=self.shop, notif_type=Notification.NotifType.CREDIT_RISK_RED
            ).count(),
            1,
        )

    def test_credit_limit_exceeded_notifies_on_crossing(self):
        self.customer.credit_limit = Decimal("300")
        self.customer.save(update_fields=["credit_limit"])

        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )

        self.assertTrue(
            Notification.objects.filter(
                shop=self.shop,
                notif_type=Notification.NotifType.CREDIT_LIMIT_EXCEEDED,
            ).exists()
        )

    def test_credit_limit_of_zero_means_no_limit(self):
        # credit_limit defaults to 0 — customers use that to mean "no limit
        # set", not "must owe nothing".
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("999999")
        )

        self.assertFalse(
            Notification.objects.filter(
                shop=self.shop,
                notif_type=Notification.NotifType.CREDIT_LIMIT_EXCEEDED,
            ).exists()
        )


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user, self.shop = make_user_with_shop("owner@example.com")
        self.other_user, self.other_shop = make_user_with_shop("intruder@example.com")
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")
        Customer.objects.create(shop=self.other_shop, name="Shyam")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_only_returns_own_shops_notifications(self):
        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for row in response.data["results"]:
            self.assertEqual(row["customer"], self.customer.id)

    def test_mark_read(self):
        notif = Notification.objects.filter(shop=self.shop).first()

        response = self.client.post(f"/api/v1/notifications/{notif.id}/mark-read/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_all_read(self):
        Payment.objects.create(customer=self.customer, amount_paid=Decimal("10"))
        unread_count = Notification.objects.filter(
            shop=self.shop, is_read=False
        ).count()
        self.assertGreater(unread_count, 0)

        response = self.client.post("/api/v1/notifications/mark-all-read/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["marked_read"], unread_count)
        self.assertEqual(
            Notification.objects.filter(shop=self.shop, is_read=False).count(), 0
        )

    def test_cannot_mark_another_shops_notification_read(self):
        other_notif = Notification.objects.filter(shop=self.other_shop).first()

        response = self.client.post(
            f"/api/v1/notifications/{other_notif.id}/mark-read/"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class NotificationEmailTests(TestCase):
    """Only CRITICAL_NOTIF_TYPES (credit_risk_red, credit_limit_exceeded)
    get an immediate email — everything else stays in-app-only until the
    daily digest picks it up (see DailyDigestTaskTests)."""

    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")
        mail.outbox.clear()  # discard the customer_added notification's (non-)email

    def test_customer_added_does_not_send_email(self):
        self.assertEqual(len(mail.outbox), 0)

    def test_credit_risk_red_sends_immediate_email(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        UdharoEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        for _ in range(3):
            Payment.objects.create(customer=self.customer, amount_paid=Decimal("10"))
        mail.outbox.clear()

        calculate_credit_score(self.customer)  # -> red (see ledger tests)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_credit_limit_exceeded_sends_immediate_email(self):
        self.customer.credit_limit = Decimal("300")
        self.customer.save(update_fields=["credit_limit"])
        mail.outbox.clear()

        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )

        self.assertEqual(len(mail.outbox), 1)


class DailyDigestTaskTests(TestCase):
    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")
        mail.outbox.clear()

    def test_sends_digest_for_shop_with_unread_notifications(self):
        result = send_daily_digests()

        self.assertEqual(result["shops_emailed"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_skips_shop_with_no_unread_notifications(self):
        Notification.objects.filter(shop=self.shop).update(is_read=True)
        mail.outbox.clear()

        result = send_daily_digests()

        self.assertEqual(result["shops_emailed"], 0)
        self.assertEqual(len(mail.outbox), 0)
