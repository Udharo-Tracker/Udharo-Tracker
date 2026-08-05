from rest_framework import serializers

from ..models import Transaction
from ..tasks.services import get_allocated_amount
from .allocation import AllocationOutSerializer, TransactionRefSerializer
from .payment import PaymentPhotoSerializer
from apps.shops.serializers.customer import CustomerSerializer


class TransactionSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    type = serializers.CharField(source="get_txn_type_display", read_only=True)
    title = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()
    udharo_entry = serializers.SerializerMethodField()
    payment = serializers.SerializerMethodField()
    parties = serializers.SerializerMethodField()
    allocations = serializers.SerializerMethodField()
    balance_after = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "txn_number",
            "type",
            "title",
            "amount",
            "status",
            "remarks",
            "transaction_date",
            "created_at",
            "customer",
            "recorded_by",
            "udharo_entry",
            "payment",
            "parties",
            "allocations",
            "balance_after",
        ]

    def get_title(self, obj):
        if obj.txn_type == Transaction.TxnType.OPENING:
            return "Opening"
        return obj.customer.name

    def get_recorded_by(self, obj):
        if not obj.recorded_by:
            return None
        full_name = f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip()
        return {
            "id": obj.recorded_by.id,
            "full_name": full_name or obj.recorded_by.email,
        }

    def get_udharo_entry(self, obj):
        if obj.txn_type != Transaction.TxnType.UDHARO or not obj.udharo_entry_id:
            return None
        entry = obj.udharo_entry
        return {
            "id": entry.id,
            "items": [
                {"item_name": item.item_name, "amount": item.amount}
                for item in entry.items.all()
            ],
        }

    def get_payment(self, obj):
        if obj.txn_type != Transaction.TxnType.PAYMENT or not obj.payment_id:
            return None
        payment = obj.payment
        return {
            "payment_mode": payment.payment_mode,
            "reference": payment.reference,
            "photos": PaymentPhotoSerializer(
                payment.photos.all(), many=True, context=self.context
            ).data,
        }

    def get_parties(self, obj):
        # Only one party per transaction today (always the customer) — this
        # stays an array so Supplier/Staff can be added as siblings later
        # without changing the response shape.
        if obj.txn_type == Transaction.TxnType.PAYMENT:
            paid_amount, unpaid_amount = obj.amount, 0
            payments = []
            allocated_from_transactions = []
        else:
            paid_amount = getattr(obj, "allocated_amount", None)
            if paid_amount is None:
                paid_amount = get_allocated_amount(obj)
            unpaid_amount = obj.amount - paid_amount

            # Both views onto the same allocations_received, kept side by
            # side: `payments` is the per-payment breakdown (with a nested
            # ref back to the source transaction); `allocated_from_transactions`
            # is the flatter "which transactions paid this off" list.
            allocations = obj.allocations_received.all()
            payments = [
                {
                    "amount": alloc.amount,
                    "write_off_amount": 0,
                    "allocated_from": TransactionRefSerializer(
                        alloc.payment_transaction, context=self.context
                    ).data,
                }
                for alloc in allocations
            ]
            allocated_from_transactions = [
                {
                    "id": alloc.payment_transaction.id,
                    "txn_number": alloc.payment_transaction.txn_number,
                    "transaction_date": alloc.payment_transaction.transaction_date,
                    "amount": alloc.amount,
                }
                for alloc in allocations
            ]

        return [
            {
                "amount": obj.amount,
                "customer": CustomerSerializer(obj.customer, context=self.context).data,
                "supplier": None,
                "staff": None,
                "paid_amount": paid_amount,
                "unpaid_amount": unpaid_amount,
                "status": obj.status,
                "payments": payments,
                "allocated_from_transactions": allocated_from_transactions,
            }
        ]

    def get_allocations(self, obj):
        if obj.txn_type != Transaction.TxnType.PAYMENT:
            return None
        return AllocationOutSerializer(
            obj.allocations_made.all(), many=True, context=self.context
        ).data

    def get_balance_after(self, obj):
        return self.context.get("balance_after_map", {}).get(obj.id)


class TransactionListSerializer(serializers.ModelSerializer):
    """Flat, ledger-style row for the transaction list endpoint — running
    debit/credit columns and cumulative closing balances, no nested
    customer/parties/allocations. Use TransactionSerializer (the detail
    serializer) to drill into one transaction."""

    type = serializers.CharField(source="get_txn_type_display", read_only=True)
    title = serializers.SerializerMethodField()
    transaction_credit = serializers.SerializerMethodField()
    transaction_debit = serializers.SerializerMethodField()
    closing_balance_credit = serializers.SerializerMethodField()
    closing_balance_debit = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "created_at",
            "transaction_date",
            "txn_number",
            "title",
            "type",
            "transaction_credit",
            "transaction_debit",
            "closing_balance_credit",
            "closing_balance_debit",
        ]

    def get_title(self, obj):
        if obj.txn_type == Transaction.TxnType.OPENING:
            return "Opening"
        return obj.customer.name

    def get_transaction_credit(self, obj):
        # A payment credits the customer's account (reduces what they owe);
        # opening/udharo debit it (increase what they owe).
        return obj.amount if obj.txn_type == Transaction.TxnType.PAYMENT else 0

    def get_transaction_debit(self, obj):
        return 0 if obj.txn_type == Transaction.TxnType.PAYMENT else obj.amount

    def _running_totals(self, obj):
        return self.context.get("running_totals_map", {}).get(obj.id, (0, 0))

    def get_closing_balance_debit(self, obj):
        return self._running_totals(obj)[0]

    def get_closing_balance_credit(self, obj):
        return self._running_totals(obj)[1]
