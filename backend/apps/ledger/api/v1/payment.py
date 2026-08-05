from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ...models import Payment, Transaction
from ...serializers.payment import PaymentSerializer
from ...tasks.services import (
    allocate_payment_fifo,
    calculate_credit_score,
    clear_ledger_cache,
    get_outstanding_balance,
    reallocate_payment,
    record_transaction,
    sync_udharo_settlement,
)


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

        # Balance from the single source of truth (includes opening_balance).
        balance = get_outstanding_balance(customer)

        if amount > balance:
            raise ValidationError(
                f"Payment of Rs.{amount} exceeds outstanding balance of Rs.{balance}."
            )

        with transaction.atomic():
            serializer.save()
            payment = serializer.instance

            payment_txn = record_transaction(
                customer=customer,
                txn_type=Transaction.TxnType.PAYMENT,
                amount=payment.amount_paid,
                user=self.request.user,
                remarks=payment.note,
                status="paid",
                transaction_date=payment.transaction_date,
                payment=payment,
            )

            # Auto-allocate this payment against the customer's oldest unpaid
            # debts first (FIFO), then resettle/unsettle entries based on
            # their own allocations and keep Transaction.status in sync.
            allocate_payment_fifo(payment_txn)
            sync_udharo_settlement(customer)

            calculate_credit_score(customer)

        clear_ledger_cache(self.request.user)

    def perform_update(self, serializer):
        payment = self.get_object()
        customer = payment.customer
        old_amount = payment.amount_paid
        new_amount = serializer.validated_data.get("amount_paid", old_amount)

        if new_amount <= 0:
            raise ValidationError("Payment amount must be positive.")

        # This payment's own amount is already counted in the pooled balance,
        # so give it back before checking the new amount fits.
        available = get_outstanding_balance(customer) + old_amount
        if new_amount > available:
            raise ValidationError(
                f"Payment of Rs.{new_amount} exceeds available outstanding "
                f"balance of Rs.{available}."
            )

        with transaction.atomic():
            payment = serializer.save()

            # Keep the audit-trail row's amount/remarks/date from going stale.
            payment_txn = Transaction.objects.get(payment=payment)
            payment_txn.amount = payment.amount_paid
            payment_txn.remarks = payment.note
            payment_txn.transaction_date = payment.transaction_date
            payment_txn.save(update_fields=["amount", "remarks", "transaction_date"])

            # Amount may have changed — redo this payment's allocations from
            # scratch against the customer's currently-unpaid debts.
            reallocate_payment(payment_txn)
            sync_udharo_settlement(customer)
            calculate_credit_score(customer)

        clear_ledger_cache(self.request.user)

    def perform_destroy(self, instance):
        customer = instance.customer

        with transaction.atomic():
            instance.delete()
            sync_udharo_settlement(customer)
            calculate_credit_score(customer)

        clear_ledger_cache(self.request.user)
