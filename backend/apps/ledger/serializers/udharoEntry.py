from rest_framework import serializers
from ..models import UdharoEntry


class UdharoEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = UdharoEntry
        fields = ['id', 'customer', 'amount', 'note', 'is_settled', 'created_at', 'settled_at']
        read_only_fields = ['created_at', 'settled_at', 'is_settled']
