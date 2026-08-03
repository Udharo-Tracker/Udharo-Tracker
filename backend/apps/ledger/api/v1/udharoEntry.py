from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.core.cache import cache
from django.db import transaction

from ...models import UdharoEntry
from ...serializers.udharoEntry import UdharoEntrySerializer
from ...tasks.services import calculate_credit_score

# Create your views here.
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
    ],
)
class UdharoEntryViewSet(viewsets.ModelViewSet):
    serializer_class = UdharoEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = UdharoEntry.objects.filter(customer__shop__owner=self.request.user)

        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        return queryset

    def _clear_user_cache(self):
        cache.delete(f"ledger_summary_{self.request.user.id}")
        cache.delete(f"dashboard_{self.request.user.id}")

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You don't own this customer.")

        with transaction.atomic():
            serializer.save()
            calculate_credit_score(customer)

        self._clear_user_cache()

    def perform_update(self, serializer):
        serializer.save()
        self._clear_user_cache()

    def perform_destroy(self, instance):
        instance.delete()
        self._clear_user_cache()
        