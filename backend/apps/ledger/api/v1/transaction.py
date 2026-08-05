from rest_framework import generics, permissions
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ...models import Transaction
from ...serializers.transaction import TransactionSerializer


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
    ],
)
class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Transaction.objects.filter(
            customer__shop__owner=self.request.user
        ).select_related("customer", "recorded_by")

        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        txn_type = self.request.query_params.get("type")
        if txn_type:
            queryset = queryset.filter(txn_type=txn_type)

        return queryset


@extend_schema(tags=["Transactions"])
class TransactionDetailView(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        return Transaction.objects.filter(
            customer__shop__owner=self.request.user
        ).select_related("customer", "recorded_by")
