from django.core.management.base import BaseCommand
from django.db import transaction

from apps.shops.models import Customer
from apps.ledger.models import Transaction
from apps.ledger.tasks.services import allocate_payment_fifo, sync_udharo_settlement


class Command(BaseCommand):
    help = (
        "One-time backfill: create Allocation rows for payment-type "
        "Transactions recorded before per-entry allocation existed, then "
        "resync each customer's opening/udharo settlement status to match. "
        "Safe to run more than once (skips payments that already have "
        "allocations)."
    )

    def handle(self, *args, **options):
        customers_touched = 0
        payments_allocated = 0

        for customer in Customer.objects.all():
            with transaction.atomic():
                payment_txns = Transaction.objects.filter(
                    customer=customer, txn_type=Transaction.TxnType.PAYMENT
                ).order_by("transaction_date", "created_at")

                any_allocated = False
                for payment_txn in payment_txns:
                    if payment_txn.allocations_made.exists():
                        continue
                    allocate_payment_fifo(payment_txn)
                    payments_allocated += 1
                    any_allocated = True

                if any_allocated:
                    sync_udharo_settlement(customer)
                    customers_touched += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Allocated {payments_allocated} payment(s) across "
                f"{customers_touched} customer(s)."
            )
        )
