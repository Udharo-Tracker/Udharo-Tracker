from rest_framework import serializers
from django.db import transaction

from ..models import UdharoEntry, UdharoEntryItem
from .UdharoEntryItem import UdharoEntryItemSerializer


class UdharoEntrySerializer(serializers.ModelSerializer):
    items = UdharoEntryItemSerializer(many=True)
    total_amount = serializers.ReadOnlyField()

    class Meta:
        model = UdharoEntry
        fields = ['id', 'customer', 'items', 'total_amount', 'note', 
                  'is_settled', 'created_at', 'settled_at']
        read_only_fields = ['created_at', 'settled_at', 'is_settled', 'total_amount']

    def create(self, validated_data):
        items_data = validated_data.pop('items')

        with transaction.atomic():
            entry = UdharoEntry.objects.create(**validated_data)
            for item in items_data:
                UdharoEntryItem.objects.create(entry=entry, **item)
        return entry