from rest_framework import serializers
from apps.shops.models import Customer
from apps.ledger.tasks.services import get_balance_breakdown


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "address",
            "credit_limit",
            "credit_term_days",
            "loyalty_discount",
            "opening_balance",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class LedgerSummarySerializer(serializers.Serializer):
    """Read-only balance figures for a customer, nested under
    CustomerDetailSerializer.ledger_summary. A plain Serializer (not a
    ModelSerializer) because it's not tied 1:1 to Customer's own fields —
    total_udharo/total_paid/outstanding_balance are computed, not stored."""

    opening_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_udharo = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()

    def _balance_value(self, obj, key):
        # If the queryset already annotated these (see services.annotate_balance),
        # use that instead of re-querying per row.
        if hasattr(obj, key):
            return getattr(obj, key)
        return get_balance_breakdown(obj)[key]

    def get_total_udharo(self, obj):
        return self._balance_value(obj, "total_udharo")

    def get_total_paid(self, obj):
        return self._balance_value(obj, "total_paid")

    def get_outstanding_balance(self, obj):
        return self._balance_value(obj, "outstanding_balance")


class CustomerDetailSerializer(CustomerSerializer):
    """Adds the balance summary that used to live on CustomerStatementView.
    Kept as a subclass rather than adding these fields to CustomerSerializer
    directly, since that base serializer is nested inside
    TransactionSerializer/PaymentSerializer/UdharoEntrySerializer — putting
    balance queries there would N+1 every row of a transaction/payment list."""

    # source="*" hands the whole Customer instance to LedgerSummarySerializer
    # instead of looking up a "ledger_summary" attribute on it.
    ledger_summary = LedgerSummarySerializer(source="*", read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + ["ledger_summary"]
        # opening_balance still needs to be a plain input field (create/update
        # read it from validated_data — see CustomerViewSet.perform_create/
        # perform_update) but is reported to the client via ledger_summary
        # instead, so drop it from the response body.
        extra_kwargs = {"opening_balance": {"write_only": True}}
