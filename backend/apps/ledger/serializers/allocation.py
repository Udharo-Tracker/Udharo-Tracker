from rest_framework import serializers

from ..models import Allocation, Transaction


class TransactionRefSerializer(serializers.ModelSerializer):
    """Minimal reference to a Transaction, used inside allocation payloads
    so we don't re-serialize the whole transaction (customer, parties, etc.)
    for something that's just pointing at another row."""

    class Meta:
        model = Transaction
        fields = ["id", "txn_number", "transaction_date"]


class AllocationOutSerializer(serializers.ModelSerializer):
    """What a payment-type transaction cleared."""

    debt_transaction = TransactionRefSerializer(read_only=True)

    class Meta:
        model = Allocation
        fields = ["debt_transaction", "amount"]
