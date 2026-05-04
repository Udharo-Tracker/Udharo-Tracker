from django.shortcuts import render
from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema

from ...models import Customer
from apps.shops.serializers.customer import CustomerSerializer

# Create your views here.
@extend_schema(tags=["Customers"])
class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(shop__owner=self.request.user)

    def perform_create(self, serializer):
        shop = self.request.user.shop
        serializer.save(shop=shop)