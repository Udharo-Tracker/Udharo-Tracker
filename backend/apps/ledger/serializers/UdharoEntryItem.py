from rest_framework import serializers
from ..models import UdharoEntryItem


class UdharoEntryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = UdharoEntryItem
        fields = ['id', 'item_name', 'amount']