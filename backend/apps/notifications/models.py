import uuid
from django.db import models

from apps.shops.models import Shop, Customer


class Notification(models.Model):
    """A system-generated activity record for a shop owner. Rows are created
    exclusively by signal handlers in signals.py, reacting to events
    elsewhere in the app (a customer being added, a payment coming in,
    etc.) — nothing writes to this model directly."""

    class NotifType(models.TextChoices):
        CUSTOMER_ADDED = "customer_added", "Customer added"
        UDHARO_CREATED = "udharo_created", "Udharo entry created"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        REMINDER_SENT = "reminder_sent", "Reminder sent"
        CREDIT_RISK_RED = "credit_risk_red", "Credit risk turned red"
        CREDIT_LIMIT_EXCEEDED = "credit_limit_exceeded", "Credit limit exceeded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Who this notification is for. Mirrors Customer's own shop-scoping so
    # the same `shop__owner=request.user` permission pattern works here too.
    shop = models.ForeignKey(
        Shop, on_delete=models.CASCADE, related_name="notifications"
    )
    # Optional link back to the customer the activity is about, so the
    # frontend can deep-link to them. Null for shop-wide notifications
    # (there aren't any yet, but nothing here requires a customer).
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    notif_type = models.CharField(max_length=30, choices=NotifType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notif_type_display()} - {self.shop.name}"
