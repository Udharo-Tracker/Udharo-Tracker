from rest_framework import viewsets, permissions
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema

from ...models import Shop
from apps.shops.serializers.shop import ShopSerializer


@extend_schema(tags=["Shops"])
class ShopViewSet(viewsets.ModelViewSet):
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Shop.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        if Shop.objects.filter(owner=self.request.user).exists():
            raise ValidationError("You already have a shop. Only one shop per account is allowed.")
        serializer.save(owner=self.request.user)