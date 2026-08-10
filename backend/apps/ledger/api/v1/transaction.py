from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import generics, permissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ...models import Allocation, Transaction
from ...filters import TransactionFilter
from ...serializers.transaction import TransactionListSerializer, TransactionSerializer
from ...tasks.services import build_balance_after_map, build_running_totals_map

# Detail view needs the full graph (customer/parties/allocations/udharo
# items/payment info); the list view is a flat ledger row and only needs
# "customer" for its title.
_DETAIL_SELECT_RELATED = ("customer", "recorded_by", "udharo_entry", "payment")
_DETAIL_PREFETCH_RELATED = (
    "udharo_entry__items",
    "payment__photos",
    "allocations_made__debt_transaction",
    "allocations_received__payment_transaction__payment__photos",
)


def _with_allocated_amount(queryset):
    allocated_sum = (
        Allocation.objects.filter(debt_transaction=OuterRef("pk"))
        .values("debt_transaction")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return queryset.annotate(
        allocated_amount=Coalesce(
            Subquery(allocated_sum), Value(0), output_field=DecimalField()
        )
    )


# NOTE: drf-spectacular can't auto-derive these from TransactionFilter here,
# because get_queryset() filters by request.user, which is AnonymousUser
# during schema generation (pre-existing across every user-scoped viewset in
# this codebase) — so the filter params are documented explicitly instead.
@extend_schema(
    tags=["Transactions"],
    parameters=[
        OpenApiParameter(
            name="customer_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter transactions by customer UUID.",
        ),
        OpenApiParameter(
            name="type",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter transactions by type: opening, udharo, or payment.",
        ),
        OpenApiParameter(
            name="status",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by status: open, closed, or paid.",
        ),
        OpenApiParameter(
            name="search",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Search transaction number/remarks (case-insensitive).",
        ),
        OpenApiParameter(
            name="date_after",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only transactions dated on/after this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="date_before",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only transactions dated on/before this date (YYYY-MM-DD).",
        ),
    ],
)
class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TransactionFilter

    def get_queryset(self):
        return Transaction.objects.filter(
            customer__shop__owner=self.request.user
        ).select_related("customer")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Running debit/credit totals only mean something scoped to one
        # customer's own transaction history, ordered oldest-first — not
        # across a multi-customer listing.
        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            context["running_totals_map"] = build_running_totals_map(customer_id)
        return context


@extend_schema(tags=["Transactions"])
class TransactionDetailView(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        queryset = (
            Transaction.objects.filter(customer__shop__owner=self.request.user)
            .select_related(*_DETAIL_SELECT_RELATED)
            .prefetch_related(*_DETAIL_PREFETCH_RELATED)
        )
        return _with_allocated_amount(queryset)

    def retrieve(self, request, *args, **kwargs):
        # The customer isn't known until the object is fetched, so build
        # balance_after_map here rather than in get_serializer_context.
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            context={
                **self.get_serializer_context(),
                "balance_after_map": build_balance_after_map(instance.customer_id),
            },
        )
        return Response(serializer.data)
