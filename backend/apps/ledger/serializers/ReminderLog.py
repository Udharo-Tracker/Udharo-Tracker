from rest_framework import serializers
from ..models import ReminderLog


class ReminderLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderLog
        fields = ['id', 'customer', 'sent_at', 'note', 'outstanding_balance']
        read_only_fields = ['id', 'customer', 'sent_at']
