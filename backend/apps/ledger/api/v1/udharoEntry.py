from rest_framework import status, viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.db import transaction

from ...models import UdharoEntry, Transaction
from ...filters import UdharoEntryFilter
from ...serializers.udharoEntry import UdharoEntrySerializer
from ...tasks.services import (
    calculate_credit_score,
    clear_ledger_cache,
    get_allocated_amount,
    get_outstanding_balance,
    record_transaction,
    sync_udharo_settlement,
    void_udharo_entry,
)


# Create your views here.
# NOTE: drf-spectacular can't auto-derive these from UdharoEntryFilter here,
# because get_queryset() filters by request.user, which is AnonymousUser
# during schema generation (pre-existing across every user-scoped viewset in
# this codebase) — so the filter params are documented explicitly instead.
@extend_schema(
    tags=["Udharo"],
    parameters=[
        OpenApiParameter(
            name="customer_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter udharo entries by customer UUID.",
        ),
        OpenApiParameter(
            name="is_settled",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by settlement state.",
        ),
        OpenApiParameter(
            name="search",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Search entry notes (case-insensitive).",
        ),
        OpenApiParameter(
            name="created_after",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only entries created on/after this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="created_before",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only entries created on/before this date (YYYY-MM-DD).",
        ),
    ],
)
class UdharoEntryViewSet(viewsets.ModelViewSet):
    serializer_class = UdharoEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = UdharoEntryFilter
    ordering_fields = ["created_at", "settled_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return UdharoEntry.objects.filter(customer__shop__owner=self.request.user)

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You don't own this customer.")

        with transaction.atomic():
            entry = serializer.save()

            # Opt-in hard stop: credit_limit alone is advisory (see the
            # credit_limit_exceeded notification signal) — this is only
            # enforced when the shop owner has explicitly turned it on.
            if customer.block_over_credit_limit and customer.credit_limit > 0:
                outstanding = get_outstanding_balance(customer)
                if outstanding > customer.credit_limit:
                    raise ValidationError(
                        f"This entry would put {customer.name}'s outstanding "
                        f"balance at Rs.{outstanding}, over their Rs."
                        f"{customer.credit_limit} credit limit."
                    )

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

    @extend_schema(
        tags=["Udharo"],
        request={
            "application/json": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
            }
        },
        description=(
            "Voids the entry instead of deleting it: it stays visible in the "
            "customer's statement (marked voided) but no longer counts toward "
            "balance/credit score. Blocked if a payment is already allocated "
            'against it. Optional JSON body: {"reason": "..."}.'
        ),
    )
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        reason = request.data.get("reason", "")

        with transaction.atomic():
            void_udharo_entry(instance, reason=reason)

        clear_ledger_cache(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
