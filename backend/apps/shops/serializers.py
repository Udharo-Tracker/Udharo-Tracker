from rest_framework import serializers
from .models import Shop, Customer


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'created_at']
        read_only_fields = ['created_at']


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ['id', 'name', 'phone', 'address', 'created_at']
        read_only_fields = ['created_at']