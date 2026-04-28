from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.ledger.views import PaymentViewSet, UdharoEntryViewSet

router = DefaultRouter()
router.register(r'udharo', UdharoEntryViewSet, basename='udharo')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path("", include(router.urls)),
]