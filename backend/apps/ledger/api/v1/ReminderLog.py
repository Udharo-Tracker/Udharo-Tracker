from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema

from apps.shops.models import Customer
from ...models import ReminderLog
from ...serializers.ReminderLog import ReminderLogSerializer


@extend_schema(tags=["Reminder Log"])
class ReminderLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        logs = ReminderLog.objects.filter(customer=customer).order_by('-sent_at')
        serializer = ReminderLogSerializer(logs, many=True)
        return Response(serializer.data)

    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        serializer = ReminderLogSerializer(data={**request.data, 'customer': customer.id})
        serializer.is_valid(raise_exception=True)
        serializer.save(customer=customer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
