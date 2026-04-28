from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Shop, Customer
from .serializers import ShopSerializer, CustomerSerializer
from drf_spectacular.utils import extend_schema

# Create your views here.

@extend_schema(tags=["Shops"])
class ShopViewSet(viewsets.ModelViewSet):
    serializer_class = ShopSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Shop.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

@extend_schema(tags=["Customers"])
class CustomerViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Customer.objects.filter(shop__owner=self.request.user)

    def perform_create(self, serializer):
        shop = self.request.user.shop
        serializer.save(shop=shop)