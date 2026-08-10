import django_filters
from django.db.models import Q

from .models import Customer


class CustomerFilter(django_filters.FilterSet):
    """Filtering/search for the customer list endpoint.

    `search` does an OR-across-fields icontains match on name/phone/email.
    """

    search = django_filters.CharFilter(method="filter_search", label="Search")
    min_credit_limit = django_filters.NumberFilter(
        field_name="credit_limit", lookup_expr="gte"
    )
    max_credit_limit = django_filters.NumberFilter(
        field_name="credit_limit", lookup_expr="lte"
    )
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Customer
        fields = []  # every filter is declared explicitly above

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(phone__icontains=value)
            | Q(email__icontains=value)
        )
