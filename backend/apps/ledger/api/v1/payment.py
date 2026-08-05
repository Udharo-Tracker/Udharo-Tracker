from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.core.cache import cache
from django.utils import timezone

from ...models import Payment, Transaction
from ...serializers.payment import PaymentSerializer
from ...tasks.services import calculate_credit_score, record_transaction


@extend_schema(
    tags=["Payments"],
    parameters=[
        OpenApiParameter(
            name="customer_id",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter payments by customer UUID.",
        ),
    ],
)
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Payment.objects.filter(customer__shop__owner=self.request.user)

        customer_id = self.request.query_params.get("customer_id")
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)

        return queryset

    def perform_create(self, serializer):
        customer = serializer.validated_data["customer"]
        amount = serializer.validated_data["amount_paid"]

        if customer.shop.owner != self.request.user:
            raise PermissionDenied("You do not own this customer.")

        if amount <= 0:
            raise ValidationError("Payment amount must be positive.")

        # Calculate real balance from source of truth (all-time entries vs
        # all-time payments, so it stays in sync regardless of settlement state)
        total_udharo = (
            customer.udharo_entries.aggregate(total=Sum("items__amount"))["total"] or 0
        )

        total_paid = customer.payments.aggregate(total=Sum("amount_paid"))["total"] or 0

        balance = total_udharo - total_paid

        if amount > balance:
            raise ValidationError(
                f"Payment of Rs.{amount} exceeds outstanding balance of Rs.{balance}."
            )

        with transaction.atomic():
            serializer.save()
            payment = serializer.instance

            # Recalculate balance after payment (all-time, see comment above)
            total_udharo = (
                customer.udharo_entries.aggregate(total=Sum("items__amount"))["total"]
                or 0
            )

            total_paid = (
                customer.payments.aggregate(total=Sum("amount_paid"))["total"] or 0
            )

            balance = total_udharo - total_paid

            # Auto settle if fully paid
            if balance == 0:
                customer.udharo_entries.filter(is_settled=False).update(
                    settled_at=timezone.now(), is_settled=True
                )

            calculate_credit_score(customer)
            record_transaction(
                customer=customer,
                txn_type=Transaction.TxnType.PAYMENT,
                amount=payment.amount_paid,
                user=self.request.user,
                remarks=payment.note,
                transaction_date=payment.created_at,
                payment=payment,
            )

        self._clear_user_cache()

    def _clear_user_cache(self):
        cache.delete(f"ledger_summary_{self.request.user.id}")
        cache.delete(f"dashboard_{self.request.user.id}")

    def perform_update(self, serializer):
        serializer.save()
        self._clear_user_cache()

    def perform_destroy(self, instance):
        instance.delete()
        self._clear_user_cache()
