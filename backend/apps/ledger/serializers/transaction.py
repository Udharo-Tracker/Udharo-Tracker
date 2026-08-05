from rest_framework import serializers

from ..models import Transaction
from apps.shops.serializers.customer import CustomerSerializer


class TransactionSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    type = serializers.CharField(source="get_txn_type_display", read_only=True)
    title = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()

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
