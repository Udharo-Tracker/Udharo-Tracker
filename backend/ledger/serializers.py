from rest_framework import serializers
from .models import UdharoEntry, Payment


class UdharoEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = UdharoEntry
        fields = ['id', 'customer', 'amount', 'note', 'is_settled', 'created_at', 'settled_at']
        read_only_fields = ['created_at', 'settled_at', 'is_settled']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'customer', 'amount_paid', 'note', 'created_at']
        read_only_fields = ['created_at']