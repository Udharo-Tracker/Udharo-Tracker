from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.account.models import User
from apps.shops.models import Customer, Shop

from .models import (
    Allocation,
    CreditScore,
    Payment,
    Transaction,
    UdharoEntry,
    UdharoEntryItem,
)
from .tasks.services import (
    calculate_credit_score,
    get_balance_breakdown,
    get_outstanding_balance,
)


def make_user_with_shop(email="owner@example.com"):
    user = User.objects.create_user(email=email, password="Str0ngPass!23")
    shop = Shop.objects.create(owner=user, name=f"{email}'s shop")
    return user, shop


class BalanceBreakdownTests(TestCase):
    """get_balance_breakdown is the single source of truth every ledger
    endpoint (dashboard, summary, statement, payment validation) reads
    balances from — this is the highest-value place for a bug to hide."""

    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.customer = Customer.objects.create(
            shop=self.shop, name="Ram", opening_balance=Decimal("100")
        )

    def test_combines_opening_udharo_and_payments(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        Payment.objects.create(customer=self.customer, amount_paid=Decimal("200"))

        breakdown = get_balance_breakdown(self.customer)

        self.assertEqual(breakdown["total_udharo"], Decimal("500"))
        self.assertEqual(breakdown["total_paid"], Decimal("200"))
        self.assertEqual(
            breakdown["outstanding_balance"], Decimal("400")
        )  # 100+500-200

    def test_settled_entries_still_count_toward_total_udharo(self):
        # total_paid is all-time, so total_udharo must be too, or a paid-off
        # entry would vanish from the total while its payment remains,
        # producing a false negative balance.
        entry = UdharoEntry.objects.create(customer=self.customer, is_settled=True)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )

        breakdown = get_balance_breakdown(self.customer)

        self.assertEqual(breakdown["total_udharo"], Decimal("500"))

    def test_voided_udharo_entry_excluded(self):
        entry = UdharoEntry.objects.create(customer=self.customer, is_voided=True)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )

        breakdown = get_balance_breakdown(self.customer)

        self.assertEqual(breakdown["total_udharo"], Decimal("0"))
        self.assertEqual(breakdown["outstanding_balance"], Decimal("100"))

    def test_voided_payment_excluded(self):
        Payment.objects.create(
            customer=self.customer, amount_paid=Decimal("50"), is_voided=True
        )

        breakdown = get_balance_breakdown(self.customer)

        self.assertEqual(breakdown["total_paid"], Decimal("0"))
        self.assertEqual(breakdown["outstanding_balance"], Decimal("100"))


class CreditScoreTests(TestCase):
    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")

    def test_green_for_clean_customer(self):
        score = calculate_credit_score(self.customer)
        self.assertEqual(score, 100)
        latest = CreditScore.objects.filter(customer=self.customer).latest(
            "calculated_at"
        )
        self.assertEqual(latest.risk_level, CreditScore.RiskChoices.GREEN)

    def test_yellow_for_thirty_day_overdue_entry(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        UdharoEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )

        score = calculate_credit_score(self.customer)

        self.assertEqual(score, 50)  # 100 - 40 (30d overdue) - 10 (outstanding)
        latest = CreditScore.objects.filter(customer=self.customer).latest(
            "calculated_at"
        )
        self.assertEqual(latest.risk_level, CreditScore.RiskChoices.YELLOW)

    def test_red_for_overdue_entry_plus_late_payments(self):
        entry = UdharoEntry.objects.create(customer=self.customer)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        UdharoEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )
        for _ in range(3):
            Payment.objects.create(customer=self.customer, amount_paid=Decimal("10"))

        score = calculate_credit_score(self.customer)

        self.assertEqual(
            score, 20
        )  # 100 - 40 (overdue) - 10 (outstanding) - 30 (3 late payments)
        latest = CreditScore.objects.filter(customer=self.customer).latest(
            "calculated_at"
        )
        self.assertEqual(latest.risk_level, CreditScore.RiskChoices.RED)

    def test_voided_entry_does_not_count_as_overdue(self):
        entry = UdharoEntry.objects.create(customer=self.customer, is_voided=True)
        UdharoEntryItem.objects.create(
            entry=entry, item_name="Rice", amount=Decimal("500")
        )
        UdharoEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=31)
        )

        score = calculate_credit_score(self.customer)

        self.assertEqual(score, 100)


class LedgerAPITests(TestCase):
    """End-to-end through the actual endpoints — exercises the FIFO
    allocation, settlement sync, void behavior, and cross-shop permission
    boundary together, the way a real request would."""

    def setUp(self):
        self.user, self.shop = make_user_with_shop("owner@example.com")
        self.other_user, self.other_shop = make_user_with_shop("intruder@example.com")
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _create_udharo(self, amount="500"):
        payload = {
            "customer_id": str(self.customer.id),
            "items": [{"item_name": "Rice", "amount": amount}],
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/v1/udharo/", payload, format="json")

    def _create_payment(self, amount="500"):
        return self.client.post(
            "/api/v1/payments/",
            {"customer_id": str(self.customer.id), "amount_paid": amount},
            format="json",
        )

    def test_create_udharo_entry_records_open_transaction(self):
        response = self._create_udharo("500")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        txn = Transaction.objects.get(
            customer=self.customer, txn_type=Transaction.TxnType.UDHARO
        )
        self.assertEqual(txn.amount, Decimal("500"))
        self.assertEqual(txn.status, "open")

    def test_payment_exceeding_balance_is_rejected(self):
        response = self._create_payment("100")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_payment_allocates_fifo_and_closes_entry(self):
        self._create_udharo("500")

        response = self._create_payment("500")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = UdharoEntry.objects.get(customer=self.customer)
        self.assertTrue(entry.is_settled)
        debt_txn = Transaction.objects.get(udharo_entry=entry)
        self.assertEqual(debt_txn.status, "closed")

    def test_partial_payment_leaves_entry_open(self):
        self._create_udharo("500")

        response = self._create_payment("200")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = UdharoEntry.objects.get(customer=self.customer)
        self.assertFalse(entry.is_settled)
        self.assertEqual(get_outstanding_balance(self.customer), Decimal("300"))

    def test_voiding_already_paid_udharo_entry_is_blocked(self):
        self._create_udharo("500")
        self._create_payment("500")
        entry = UdharoEntry.objects.get(customer=self.customer)

        response = self.client.delete(f"/api/v1/udharo/{entry.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        entry.refresh_from_db()
        self.assertFalse(entry.is_voided)

    def test_voiding_unpaid_udharo_entry_removes_it_from_balance_but_keeps_the_row(
        self,
    ):
        self._create_udharo("500")
        entry = UdharoEntry.objects.get(customer=self.customer)

        response = self.client.delete(
            f"/api/v1/udharo/{entry.id}/", {"reason": "duplicate entry"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        entry.refresh_from_db()
        self.assertTrue(entry.is_voided)
        self.assertEqual(entry.void_reason, "duplicate entry")
        self.assertEqual(get_outstanding_balance(self.customer), Decimal("0"))
        # Still there — voiding is not deleting.
        self.assertTrue(UdharoEntry.objects.filter(pk=entry.id).exists())
        self.assertTrue(Transaction.objects.filter(udharo_entry=entry).exists())

    def test_voiding_payment_reverses_allocation_and_reopens_entry(self):
        self._create_udharo("500")
        self._create_payment("500")
        payment = Payment.objects.get(customer=self.customer)
        entry = UdharoEntry.objects.get(customer=self.customer)
        self.assertTrue(entry.is_settled)

        response = self.client.delete(f"/api/v1/payments/{payment.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        payment.refresh_from_db()
        entry.refresh_from_db()
        self.assertTrue(payment.is_voided)
        self.assertFalse(entry.is_settled)
        self.assertEqual(
            Allocation.objects.filter(payment_transaction__payment=payment).count(), 0
        )
        self.assertEqual(get_outstanding_balance(self.customer), Decimal("500"))

    def test_cannot_reduce_udharo_entry_below_allocated_amount(self):
        response = self._create_udharo("500")
        entry_id = response.data["id"]
        self._create_payment("500")

        response = self.client.patch(
            f"/api/v1/udharo/{entry_id}/",
            {"items": [{"item_name": "Rice", "amount": "100"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_access_another_shops_customer(self):
        self.client.force_authenticate(self.other_user)

        response = self.client.get(f"/api/v1/customers/{self.customer.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_create_udharo_entry_for_another_shops_customer(self):
        self.client.force_authenticate(self.other_user)

        response = self.client.post(
            "/api/v1/udharo/",
            {
                "customer_id": str(self.customer.id),
                "items": [{"item_name": "Rice", "amount": "500"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_udharo_list_is_paginated(self):
        response = self.client.get("/api/v1/udharo/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_payments_list_can_be_ordered(self):
        self._create_payment("100")
        self._create_payment("500")

        response = self.client.get("/api/v1/payments/", {"ordering": "amount_paid"})

        amounts = [Decimal(row["amount_paid"]) for row in response.data["results"]]
        self.assertEqual(amounts, sorted(amounts))

        response = self.client.get("/api/v1/payments/", {"ordering": "-amount_paid"})

        amounts = [Decimal(row["amount_paid"]) for row in response.data["results"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_whatsapp_reminder_creates_log_entry(self):
        self.customer.phone = "9800000000"
        self.customer.save(update_fields=["phone"])
        self._create_udharo("500")

        response = self.client.post(
            f"/api/v1/customers/{self.customer.id}/reminders/whatsapp/"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        from .models import ReminderLog

        log = ReminderLog.objects.get(customer=self.customer)
        self.assertEqual(log.channel, ReminderLog.Channel.WHATSAPP)
        self.assertEqual(log.delivery_status, "sent")


class CreditLimitHardStopTests(TestCase):
    """credit_limit alone stays advisory (see the credit_limit_exceeded
    notification) — the hard stop is opt-in via block_over_credit_limit."""

    def setUp(self):
        self.user, self.shop = make_user_with_shop()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _create_udharo(self, customer, amount):
        payload = {
            "customer_id": str(customer.id),
            "items": [{"item_name": "Rice", "amount": amount}],
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/v1/udharo/", payload, format="json")

    def test_blocks_entry_that_would_exceed_limit_when_opted_in(self):
        customer = Customer.objects.create(
            shop=self.shop,
            name="Ram",
            credit_limit=Decimal("1000"),
            block_over_credit_limit=True,
        )
        self._create_udharo(customer, "500")

        response = self._create_udharo(customer, "600")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(get_outstanding_balance(customer), Decimal("500"))

    def test_allows_entry_over_limit_when_not_opted_in(self):
        customer = Customer.objects.create(
            shop=self.shop,
            name="Ram",
            credit_limit=Decimal("1000"),
            block_over_credit_limit=False,
        )
        self._create_udharo(customer, "500")

        response = self._create_udharo(customer, "600")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(get_outstanding_balance(customer), Decimal("1100"))

    def test_entry_within_limit_is_allowed(self):
        customer = Customer.objects.create(
            shop=self.shop,
            name="Ram",
            credit_limit=Decimal("1000"),
            block_over_credit_limit=True,
        )

        response = self._create_udharo(customer, "500")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PDFExportTests(TestCase):
    def setUp(self):
        self.user, self.shop = make_user_with_shop("owner@example.com")
        self.other_user, self.other_shop = make_user_with_shop("intruder@example.com")
        self.customer = Customer.objects.create(shop=self.shop, name="Ram")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _create_udharo(self, amount="500"):
        payload = {
            "customer_id": str(self.customer.id),
            "items": [{"item_name": "Rice", "amount": amount}],
        }
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post("/api/v1/udharo/", payload, format="json")

    def test_customer_statement_pdf(self):
        self._create_udharo("500")
        self._create_payment_direct("200")

        response = self.client.get(
            f"/api/v1/customers/{self.customer.id}/statement/pdf/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def _create_payment_direct(self, amount):
        return self.client.post(
            "/api/v1/payments/",
            {"customer_id": str(self.customer.id), "amount_paid": amount},
            format="json",
        )

    def test_cannot_download_another_shops_customer_statement(self):
        self.client.force_authenticate(self.other_user)

        response = self.client.get(
            f"/api/v1/customers/{self.customer.id}/statement/pdf/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_monthly_report_pdf_year_summary(self):
        self._create_udharo("500")

        response = self.client.get(
            "/api/v1/ledger/monthly-report/pdf/", {"year": timezone.now().year}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_monthly_report_pdf_month_detail(self):
        self._create_udharo("500")
        now = timezone.now()

        response = self.client.get(
            "/api/v1/ledger/monthly-report/pdf/",
            {"year": now.year, "month": now.month},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_monthly_report_pdf_requires_year(self):
        response = self.client.get("/api/v1/ledger/monthly-report/pdf/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
