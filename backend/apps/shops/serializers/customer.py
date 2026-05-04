from rest_framework import serializers
from apps.shops.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'created_at']
        read_only_fields = ['created_at']
