from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from drf_spectacular.utils import extend_schema
from django.core.cache import cache
from django.utils import timezone

from ...models import Payment
from ...serializers.payment import PaymentSerializer
from ...tasks.services import calculate_credit_score

@extend_schema(tags=["Payments"])
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(customer__shop__owner=self.request.user)

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]
        amount = serializer.validated_data["amount_paid"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You do not own this customer.")

        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")

        # Calculate real balance from source of truth
        total_udharo = customer.udharo_entries.filter(
        is_settled=False
        ).aggregate(
            total=Sum('items__amount')
        )['total'] or 0

        total_paid = customer.payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0

        balance = total_udharo - total_paid

        if amount > balance:
            raise ValidationError(
                f"Payment of Rs.{amount} exceeds outstanding balance of Rs.{balance}."
            )

        with transaction.atomic():
            serializer.save()

            # Recalculate balance after payment
            total_udharo = customer.udharo_entries.filter(
                is_settled=False
            ).aggregate(total=Sum('items__amount'))['total'] or 0
            
            total_paid = customer.payments.aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            
            balance = total_udharo - total_paid
            
            # Auto settle if fully paid
            if balance == 0:
                customer.udharo_entries.filter(
                    is_settled=False
                ).update(settled_at=timezone.now(), is_settled=True)   

            calculate_credit_score(customer)         
        
        cache.delete(f"ledger_summary_{self.request.user.id}")
        cache.delete(f"dashboard_{self.request.user.id}")
