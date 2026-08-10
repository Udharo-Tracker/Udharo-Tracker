from rest_framework import serializers
from ..models import Shop


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            "id",
            "name",
            "legal_name",
            "tax_number",
            "logo",
            "phone",
            "address",
            "created_at",
        ]
        read_only_fields = ["created_at"]
