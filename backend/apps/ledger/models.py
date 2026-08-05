from django.db import models
from django.db.models import Sum
import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.shops.models import Customer, Shop

# Create your models here.


class UdharoEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="udharo_entries"
    )
    note = models.TextField(blank=True)
    is_settled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    @property
    def total_amount(self):
        return self.items.aggregate(total=Sum("amount"))["total"] or 0

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.total_amount}"


class UdharoEntryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(
        UdharoEntry, on_delete=models.CASCADE, related_name="items"
    )
    item_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item_name} - Rs.{self.amount}"


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="payments"
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.amount_paid}"


class ReminderLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Channel(models.TextChoices):
        NOTE = "note", "Note"
        SMS = "sms", "SMS"
        AUTO = "auto", "Automatic"

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="reminder_log"
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2)
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.NOTE
    )
    delivery_status = models.CharField(max_length=10, blank=True)


class CreditScore(models.Model):

    class RiskChoices(models.TextChoices):
        GREEN = "green", "Green"
        YELLOW = "yellow", "Yellow"
        RED = "red", "Red"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="credit_scores"
    )
    calculated_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskChoices.choices,
    )


class TransactionCounter(models.Model):
    """Per-shop, per-type sequence used to generate txn_number (OP-1, UD-4, PI-3...)."""

    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="txn_counters"
    )
    txn_type = models.CharField(max_length=10)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("shop", "txn_type")

    def __str__(self):
        return f"{self.shop.name} - {self.txn_type} - {self.last_number}"


class Transaction(models.Model):
    """Read-facing audit trail row created alongside a Customer's opening
    balance, a UdharoEntry, or a Payment. Nothing writes to this directly —
    it's always a side effect of one of those three creations."""

    class TxnType(models.TextChoices):
        OPENING = "opening", "Opening"
        UDHARO = "udharo", "Udharo"
        PAYMENT = "payment", "Payment"

    TXN_PREFIX = {
        TxnType.OPENING: "OP",
        TxnType.UDHARO: "UD",
        TxnType.PAYMENT: "PI",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="transactions"
    )
    txn_type = models.CharField(max_length=10, choices=TxnType.choices)
    txn_number = models.CharField(max_length=20, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, blank=True)
    remarks = models.TextField(blank=True)
    transaction_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Exactly one of these is set, matching txn_type; both null for "opening".
    udharo_entry = models.OneToOneField(
        UdharoEntry,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="transaction",
    )
    payment = models.OneToOneField(
        Payment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="transaction",
    )

    class Meta:
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        return f"{self.txn_number} - {self.customer.name} - Rs.{self.amount}"
