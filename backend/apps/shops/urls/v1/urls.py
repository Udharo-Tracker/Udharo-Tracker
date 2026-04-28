from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.shops.views import CustomerViewSet, ShopViewSet

router = DefaultRouter()
router.register(r'shop', ShopViewSet, basename='shop')
router.register(r'customers', CustomerViewSet, basename='customer')

urlpatterns = [
    path("", include(router.urls)),
]