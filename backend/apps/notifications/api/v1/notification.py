from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter

from ...models import Notification
from ...filters import NotificationFilter
from ...serializers import NotificationSerializer


# Read-only: rows are only ever created by apps/notifications/signals.py.
# NOTE: drf-spectacular can't auto-derive these from NotificationFilter here,
# because get_queryset() filters by request.user, which is AnonymousUser
# during schema generation (pre-existing across every user-scoped viewset in
# this codebase) — so the filter params are documented explicitly instead.
@extend_schema(
    tags=["Notifications"],
    parameters=[
        OpenApiParameter(
            name="is_read",
            type=bool,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by read state.",
        ),
        OpenApiParameter(
            name="notif_type",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by notification type, e.g. payment_received.",
        ),
        OpenApiParameter(
            name="created_after",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only notifications created on/after this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="created_before",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only notifications created on/before this date (YYYY-MM-DD).",
        ),
    ],
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = NotificationFilter
    ordering_fields = ["created_at", "is_read"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Notification.objects.filter(shop__owner=self.request.user)

    @extend_schema(
        tags=["Notifications"],
        request=None,
        responses=NotificationSerializer,
        description="Marks a single notification as read.",
    )
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        tags=["Notifications"],
        request=None,
        responses=None,
        description="Marks every unread notification for this shop as read.",
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated})
