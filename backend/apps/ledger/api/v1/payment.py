from django.shortcuts import render
from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from drf_spectacular.utils import extend_schema

from ...models import Payment
from ...serializers.payment import PaymentSerializer


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
        total_udharo = customer.udharo_entries.aggregate(
            total=Sum('amount')
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