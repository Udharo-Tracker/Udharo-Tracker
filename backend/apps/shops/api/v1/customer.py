from django.shortcuts import render
from django.core.cache import cache
from django.db import transaction
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema

from ...models import Customer
from apps.shops.serializers.customer import CustomerSerializer
from apps.ledger.models import Transaction
from apps.ledger.tasks.services import record_transaction


# Create your views here.
@extend_schema(tags=["Customers"])
class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(shop__owner=self.request.user)

    def _invalidate_ledger_cache(self):
        cache.delete(f"ledger_summary_{self.request.user.id}")
        cache.delete(f"dashboard_{self.request.user.id}")

    def perform_create(self, serializer):
        shop = self.request.user.shop

        with transaction.atomic():
            customer = serializer.save(shop=shop)
            if customer.opening_balance:
                record_transaction(
                    customer=customer,
                    txn_type=Transaction.TxnType.OPENING,
                    amount=customer.opening_balance,
                    user=self.request.user,
                    remarks="Opening balance",
                    transaction_date=customer.created_at,
                )

        self._invalidate_ledger_cache()

    def perform_update(self, serializer):
        serializer.save()
        self._invalidate_ledger_cache()

    def perform_destroy(self, instance):
        instance.delete()
        self._invalidate_ledger_cache()
