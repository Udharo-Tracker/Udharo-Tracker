from rest_framework import serializers
from apps.shops.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'email', 'address',
            'credit_limit', 'credit_term_days', 'loyalty_discount',
            'opening_balance', 'created_at',
        ]
        read_only_fields = ['created_at']
