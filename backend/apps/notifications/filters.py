import django_filters

from .models import Notification


class NotificationFilter(django_filters.FilterSet):
    is_read = django_filters.BooleanFilter(field_name="is_read")
    notif_type = django_filters.ChoiceFilter(choices=Notification.NotifType.choices)
    created_after = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__gte"
    )
    created_before = django_filters.DateFilter(
        field_name="created_at", lookup_expr="date__lte"
    )

    class Meta:
        model = Notification
        fields = []
