from rest_framework.routers import DefaultRouter
from django.urls import include, path


from apps.ledger.api.v1.payment import PaymentViewSet
from apps.ledger.api.v1.udharoEntry import UdharoEntryViewSet
from apps.ledger.api.v1.customerStatement import CustomerStatementView
from apps.ledger.api.v1.ledgerSummery import LedgerSummaryView

router = DefaultRouter()
router.register(r'udharo', UdharoEntryViewSet, basename='udharo')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path("", include(router.urls)),
    path(
    "customers/<uuid:customer_id>/statement/",
    CustomerStatementView.as_view(),
    name="customer-statement",
    ),
    path(
    "/ledger/summary/",
    LedgerSummaryView.as_view(),
    name="ledger-summary",
    ),
]