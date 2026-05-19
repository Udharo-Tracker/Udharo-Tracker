from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from django.db import transaction

from ...models import UdharoEntry
from ...serializers.udharoEntry import UdharoEntrySerializer
from ...tasks.services import calculate_credit_score

# Create your views here.
@extend_schema(tags=["Udharo"])
class UdharoEntryViewSet(viewsets.ModelViewSet):
    serializer_class = UdharoEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UdharoEntry.objects.filter(customer__shop__owner=self.request.user)

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You don't own this customer.")
        
        with transaction.atomic():
            serializer.save()
            calculate_credit_score(customer)
       
        cache.delete(f"ledger_summary_{self.request.user.id}")
        cache.delete(f"dashboard_{self.request.user.id}")
        