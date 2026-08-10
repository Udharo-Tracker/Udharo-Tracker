import django_filters
from django.db.models import Q

from .models import CreditScore, Payment, ReminderLog, Transaction, UdharoEntry


class UdharoEntryFilter(django_filters.FilterSet):
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    is_settled = django_filters.BooleanFilter(field_name="is_settled")
    search = django_filters.CharFilter(field_name="note", lookup_expr="icontains")
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )

    class Meta:
        model = UdharoEntry
        fields = []


class PaymentFilter(django_filters.FilterSet):
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    payment_mode = django_filters.ChoiceFilter(choices=Payment.PaymentMode.choices)
    search = django_filters.CharFilter(method="filter_search", label="Search")
    date_after = django_filters.DateFilter(
        field_name="transaction_date", lookup_expr="date__gte"
    )
    date_before = django_filters.DateFilter(
        field_name="transaction_date", lookup_expr="date__lte"
    )

    class Meta:
        model = Payment
        fields = []

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(reference__icontains=value) | Q(note__icontains=value))


class TransactionFilter(django_filters.FilterSet):
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    # Query param kept as "type" (not "txn_type") for backward compatibility
    # with the previous hand-rolled param name.
    type = django_filters.ChoiceFilter(
        field_name="txn_type", choices=Transaction.TxnType.choices
    )
    status = django_filters.CharFilter(field_name="status", lookup_expr="exact")
    search = django_filters.CharFilter(method="filter_search", label="Search")
    date_after = django_filters.DateFilter(
        field_name="transaction_date", lookup_expr="date__gte"
    )
    date_before = django_filters.DateFilter(
        field_name="transaction_date", lookup_expr="date__lte"
    )

    class Meta:
        model = Transaction
        fields = []

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(txn_number__icontains=value) | Q(remarks__icontains=value)
        )


class CreditScoreFilter(django_filters.FilterSet):
    risk_level = django_filters.ChoiceFilter(choices=CreditScore.RiskChoices.choices)
    date_after = django_filters.DateFilter(
        field_name="calculated_at", lookup_expr="date__gte"
    )
    date_before = django_filters.DateFilter(
        field_name="calculated_at", lookup_expr="date__lte"
    )

    class Meta:
        model = CreditScore
        fields = []


class ReminderLogFilter(django_filters.FilterSet):
    channel = django_filters.ChoiceFilter(choices=ReminderLog.Channel.choices)
    delivery_status = django_filters.CharFilter(
        field_name="delivery_status", lookup_expr="exact"
    )
    search = django_filters.CharFilter(field_name="note", lookup_expr="icontains")
    date_after = django_filters.DateFilter(
        field_name="sent_at", lookup_expr="date__gte"
    )
    date_before = django_filters.DateFilter(
        field_name="sent_at", lookup_expr="date__lte"
    )

    class Meta:
        model = ReminderLog
        fields = []
