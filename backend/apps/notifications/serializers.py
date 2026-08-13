from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(
        source="customer.name", read_only=True, default=None
    )

    class Meta:
        model = Notification
        # Fully read-only through the API: rows are only ever created by
        # signals.py, and is_read only ever changes via the mark-read/
        # mark-all-read actions on NotificationViewSet.
        fields = [
            "id",
            "notif_type",
            "title",
            "message",
            "customer",
            "customer_name",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields
