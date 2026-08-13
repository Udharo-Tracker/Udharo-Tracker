"""Wires every notification trigger to the model event it reacts to.

All of this is post_save-driven and lives here instead of inside the
views/serializers that create Customer/UdharoEntry/Payment/etc rows, so a
notification fires no matter *how* the row gets created (API, admin, shell,
a future management command) and the ledger/shops apps stay unaware
notifications even exist.

Connected once, at app startup, by NotificationsConfig.ready().
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.shops.models import Customer
from apps.ledger.models import (
    CreditScore,
    Payment,
    ReminderLog,
    UdharoEntry,
    UdharoEntryItem,
)
from apps.ledger.tasks.services import get_outstanding_balance

from .models import Notification
from .services import create_notification


@receiver(post_save, sender=Customer)
def notify_customer_added(sender, instance, created, **kwargs):
    if not created:
        return
    create_notification(
        shop=instance.shop,
        customer=instance,
        notif_type=Notification.NotifType.CUSTOMER_ADDED,
        title="New customer added",
        message=f"{instance.name} was added as a customer.",
    )


@receiver(post_save, sender=UdharoEntry)
def notify_udharo_entry_created(sender, instance, created, **kwargs):
    if not created:
        return

    # instance.total_amount aggregates over instance.items, which are
    # created in a loop right after the entry itself (see
    # UdharoEntrySerializer.create) — still inside the same
    # transaction.atomic() block. Deferring to on_commit means this runs
    # after every item exists (accurate total) and only if the whole
    # request actually succeeds (rolled-back entries never notify).
    def notify():
        create_notification(
            shop=instance.customer.shop,
            customer=instance.customer,
            notif_type=Notification.NotifType.UDHARO_CREATED,
            title="New udharo entry",
            message=(
                f"Rs.{instance.total_amount} recorded for {instance.customer.name}."
            ),
        )

    transaction.on_commit(notify)


@receiver(post_save, sender=Payment)
def notify_payment_received(sender, instance, created, **kwargs):
    if not created:
        return
    create_notification(
        shop=instance.customer.shop,
        customer=instance.customer,
        notif_type=Notification.NotifType.PAYMENT_RECEIVED,
        title="Payment received",
        message=f"Rs.{instance.amount_paid} received from {instance.customer.name}.",
    )


@receiver(post_save, sender=ReminderLog)
def notify_reminder_sent(sender, instance, created, **kwargs):
    if not created:
        return
    create_notification(
        shop=instance.customer.shop,
        customer=instance.customer,
        notif_type=Notification.NotifType.REMINDER_SENT,
        title="Reminder sent",
        message=(
            f"Reminder sent to {instance.customer.name} for Rs.{instance.outstanding_balance} "
            f"outstanding."
        ),
    )


@receiver(post_save, sender=CreditScore)
def notify_credit_risk_red(sender, instance, created, **kwargs):
    """CreditScore rows are an append-only history (a new row per
    recalculation, never an update — see calculate_credit_score), so
    without this check a customer stuck at red would get a fresh
    notification every single day the recalculation task runs. Only notify
    on the transition into red."""
    if not created or instance.risk_level != CreditScore.RiskChoices.RED:
        return

    customer = instance.customer
    previous = (
        CreditScore.objects.filter(customer=customer)
        .exclude(pk=instance.pk)
        .order_by("-calculated_at")
        .first()
    )
    if previous and previous.risk_level == CreditScore.RiskChoices.RED:
        return

    create_notification(
        shop=customer.shop,
        customer=customer,
        notif_type=Notification.NotifType.CREDIT_RISK_RED,
        title="Customer credit risk turned red",
        message=f"{customer.name}'s credit risk is now red.",
    )


@receiver(post_save, sender=UdharoEntryItem)
def notify_credit_limit_exceeded(sender, instance, created, **kwargs):
    """Fires only on the item that pushes the customer's outstanding
    balance past their credit_limit, not on every save afterwards."""
    if not created:
        return

    customer = instance.entry.customer
    # credit_limit defaults to 0, which customers use to mean "no limit set"
    # rather than "must owe nothing" — skip those.
    if customer.credit_limit <= 0:
        return

    outstanding = get_outstanding_balance(customer)
    outstanding_before = outstanding - instance.amount

    if outstanding_before <= customer.credit_limit < outstanding:
        create_notification(
            shop=customer.shop,
            customer=customer,
            notif_type=Notification.NotifType.CREDIT_LIMIT_EXCEEDED,
            title="Credit limit exceeded",
            message=(
                f"{customer.name}'s outstanding balance (Rs.{outstanding}) has "
                f"exceeded their credit limit of Rs.{customer.credit_limit}."
            ),
        )
