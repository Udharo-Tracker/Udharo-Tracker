from rest_framework.routers import DefaultRouter
from django.urls import include, path


from apps.ledger.api.v1.payment import PaymentViewSet
from apps.ledger.api.v1.udharoEntry import UdharoEntryViewSet
from apps.ledger.api.v1.customerStatement import CustomerStatementView
from apps.ledger.api.v1.ledgerSummery import LedgerSummaryView
from apps.ledger.api.v1.CreditScore import CustomerCreditScoreHistoryView, CustomerCreditScoreView
from apps.ledger.api.v1.Dashboard import DashboardView
from apps.ledger.api.v1.monthlyReport import MonthlyReportView
from apps.ledger.api.v1.ReminderLog import ReminderLogView


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
    "ledger/summary/",
    LedgerSummaryView.as_view(),
    name="ledger-summary",
    ),
    path("customers/<uuid:customer_id>/credit-score/", CustomerCreditScoreView.as_view(), name="customer-credit-score"),
    path("customers/<uuid:customer_id>/credit-score/history/", CustomerCreditScoreHistoryView.as_view(), name="customer-credit-score-history"),
    path("ledger/dashboard/", DashboardView.as_view(), name="dashboard"),
    path("ledger/monthly-report/", MonthlyReportView.as_view(), name="monthly-report"),
    path("customers/<uuid:customer_id>/reminders/", ReminderLogView.as_view(), name="reminder-log"),
]