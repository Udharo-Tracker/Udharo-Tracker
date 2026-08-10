from django.shortcuts import render
from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ...models import Customer
from ...filters import CustomerFilter
from apps.shops.serializers.customer import CustomerSerializer, CustomerDetailSerializer
from apps.ledger.models import Transaction
from apps.ledger.tasks.services import (
    annotate_balance,
    calculate_credit_score,
    clear_ledger_cache,
    get_allocated_amount,
    record_transaction,
    sync_udharo_settlement,
)


# Create your views here.
# NOTE: drf-spectacular can't auto-derive these from CustomerFilter here,
# because get_queryset() filters by request.user, which is AnonymousUser
# during schema generation (pre-existing across every user-scoped viewset in
# this codebase) — so the filter params are documented explicitly instead.
@extend_schema(
    tags=["Customers"],
    parameters=[
        OpenApiParameter(
            name="search",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Search customers by name, phone, or email (case-insensitive).",
        ),
        OpenApiParameter(
            name="min_credit_limit",
            type=float,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only customers with credit_limit >= this value.",
        ),
        OpenApiParameter(
            name="max_credit_limit",
            type=float,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only customers with credit_limit <= this value.",
        ),
        OpenApiParameter(
            name="created_after",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only customers created on/after this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="created_before",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only customers created on/before this date (YYYY-MM-DD).",
        ),
    ],
)
class CustomerViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = CustomerFilter

    def get_serializer_class(self):
        # List rows are plain customer fields only — no ledger_summary — so
        # a page of customers doesn't pay for a balance calculation per row.
        # Every other action (retrieve/create/update) returns the full
        # detail shape, including ledger_summary.
        if self.action == "list":
            return CustomerSerializer
        return CustomerDetailSerializer

    def get_queryset(self):
        queryset = Customer.objects.filter(shop__owner=self.request.user)
        if self.action == "list":
            return queryset
        return annotate_balance(queryset)

    def perform_create(self, serializer):
        shop = self.request.user.shop

        with transaction.atomic():
            customer = serializer.save(shop=shop)
            # Always record an opening transaction, even at Rs.0 — every
            # customer gets an anchor row in their transaction history from
            # the moment they're created, not just customers who start with
            # a nonzero balance.
            record_transaction(
                customer=customer,
                txn_type=Transaction.TxnType.OPENING,
                amount=customer.opening_balance,
                user=self.request.user,
                remarks="Opening balance",
                transaction_date=customer.created_at,
            )
            # Sets this new opening transaction's initial status ("open"/"closed").
            sync_udharo_settlement(customer)

        clear_ledger_cache(self.request.user)

    def perform_update(self, serializer):
        customer = self.get_object()
        new_opening = serializer.validated_data.get(
            "opening_balance", customer.opening_balance
        )

        with transaction.atomic():
            opening_txn = Transaction.objects.select_for_update().get(
                customer=customer, txn_type=Transaction.TxnType.OPENING
            )
            allocated = get_allocated_amount(opening_txn)
            if new_opening < allocated:
                raise ValidationError(
                    {
                        "opening_balance": (
                            f"Cannot reduce opening balance below Rs.{allocated}; "
                            f"that much is already allocated against it."
                        )
                    }
                )

            customer = serializer.save()

            # opening_balance is editable via this serializer and feeds
            # directly into the balance/settlement/credit-score calculations,
            # so keep the linked OPENING Transaction's amount from going
            # stale and re-sync everything downstream.
            opening_txn.amount = customer.opening_balance
            opening_txn.save(update_fields=["amount"])

            sync_udharo_settlement(customer)
            calculate_credit_score(customer)

        clear_ledger_cache(self.request.user)

    def perform_destroy(self, instance):
        instance.delete()
        clear_ledger_cache(self.request.user)
