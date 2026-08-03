from rest_framework import serializers
from ..models import Payment
from apps.shops.models import Customer
from apps.shops.serializers.customer import CustomerSerializer


class PaymentSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), source='customer', write_only=True
    )

    class Meta:
        model = Payment
        fields = ['id', 'customer', 'customer_id', 'amount_paid', 'note', 'created_at']
        read_only_fields = ['created_at']