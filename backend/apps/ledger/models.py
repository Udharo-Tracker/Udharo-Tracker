from django.db import models
from django.db.models import Sum
import uuid
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.shops.models import Customer


# Create your models here.

class UdharoEntry(models.Model):
    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='udharo_entries')
    note = models.TextField(blank=True)
    is_settled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    @property
    def total_amount(self):
        return self.items.aggregate(
            total=Sum("amount")
        )["total"] or 0

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.total_amount}"

class UdharoEntryItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry = models.ForeignKey(UdharoEntry, on_delete=models.CASCADE, related_name='items')
    item_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.item_name} - Rs.{self.amount}"

class Payment(models.Model):
    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.amount_paid}"
    


class ReminderLog(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    class Channel(models.TextChoices):
        NOTE = "note", "Note"
        SMS = "sms", "SMS"
        AUTO = "auto", "Automatic"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reminder_log')
    sent_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.NOTE)
    delivery_status = models.CharField(max_length=10, blank=True)


class CreditScore(models.Model):

    class RiskChoices(models.TextChoices):
        GREEN = "green", "Green"
        YELLOW = "yellow", "Yellow"
        RED = "red", "Red"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='credit_scores')
    calculated_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(
    validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskChoices.choices,
    )

