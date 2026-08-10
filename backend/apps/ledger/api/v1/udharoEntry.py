from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from django.db import transaction

from ...models import UdharoEntry, Transaction
from ...filters import UdharoEntryFilter
from ...serializers.udharoEntry import UdharoEntrySerializer
from ...tasks.services import (
    calculate_credit_score,
    clear_ledger_cache,
    get_allocated_amount,
    record_transaction,
    sync_udharo_settlement,
)


# Create your views here.
@extend_schema(tags=["Udharo"])
class UdharoEntryViewSet(viewsets.ModelViewSet):
    serializer_class = UdharoEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UdharoEntryFilter

    def get_queryset(self):
        return UdharoEntry.objects.filter(customer__shop__owner=self.request.user)

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You don't own this customer.")

        with transaction.atomic():
            entry = serializer.save()
            calculate_credit_score(customer)
            record_transaction(
                customer=customer,
                txn_type=Transaction.TxnType.UDHARO,
                amount=entry.total_amount,
                user=self.request.user,
                remarks=entry.note,
                transaction_date=entry.created_at,
                udharo_entry=entry,
                status="open",
            )

        clear_ledger_cache(self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            entry = serializer.save()

            debt_txn = Transaction.objects.get(udharo_entry=entry)
            allocated = get_allocated_amount(debt_txn)
            if entry.total_amount < allocated:
                raise ValidationError(
                    f"Cannot reduce udharo entry to Rs.{entry.total_amount}; "
                    f"Rs.{allocated} is already paid against it."
                )

            # Keep the audit-trail row's amount/remarks from going stale.
            debt_txn.amount = entry.total_amount
            debt_txn.remarks = entry.note
            debt_txn.save(update_fields=["amount", "remarks"])

            sync_udharo_settlement(entry.customer)
            calculate_credit_score(entry.customer)

        clear_ledger_cache(self.request.user)

    def perform_destroy(self, instance):
        customer = instance.customer

        with transaction.atomic():
            instance.delete()
            sync_udharo_settlement(customer)
            calculate_credit_score(customer)

        clear_ledger_cache(self.request.user)
