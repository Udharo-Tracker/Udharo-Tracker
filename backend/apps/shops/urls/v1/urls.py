from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.shops.api.v1.customer import CustomerViewSet
from apps.shops.api.v1.shop import ShopViewSet

router = DefaultRouter()
router.register(r'shop', ShopViewSet, basename='shop')
router.register(r'customers', CustomerViewSet, basename='customer')

urlpatterns = [
    path("", include(router.urls)),
]