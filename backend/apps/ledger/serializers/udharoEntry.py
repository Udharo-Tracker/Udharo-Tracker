from rest_framework import serializers
from django.db import transaction

from ..models import UdharoEntry, UdharoEntryItem
from .UdharoEntryItem import UdharoEntryItemSerializer
from apps.shops.models import Customer
from apps.shops.serializers.customer import CustomerSerializer


class UdharoEntrySerializer(serializers.ModelSerializer):
    items = UdharoEntryItemSerializer(many=True)
    total_amount = serializers.ReadOnlyField()
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source='customer', write_only=True
    )

    class Meta:
        model = UdharoEntry
        fields = ['id', 'customer', 'customer_id', 'items', 'total_amount', 'note',
                  'is_settled', 'created_at', 'settled_at']
        read_only_fields = ['created_at', 'settled_at', 'is_settled', 'total_amount']

    def create(self, validated_data):
        items_data = validated_data.pop('items')

        with transaction.atomic():
            entry = UdharoEntry.objects.create(**validated_data)
            for item in items_data:
                UdharoEntryItem.objects.create(entry=entry, **item)
        return entry