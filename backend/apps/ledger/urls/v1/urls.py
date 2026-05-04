from rest_framework.routers import DefaultRouter
from django.urls import include, path


from apps.ledger.api.v1.payment import PaymentViewSet
from apps.ledger.api.v1.udharoEntry import UdharoEntryViewSet

router = DefaultRouter()
router.register(r'udharo', UdharoEntryViewSet, basename='udharo')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path("", include(router.urls)),
]