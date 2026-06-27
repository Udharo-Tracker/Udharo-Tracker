from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from django.db.models import Sum

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
        

        # Calculate balance automatically
        total_udharo = customer.udharo_entries.filter(
            is_settled=False
        ).aggregate(total=Sum('items__amount'))['total'] or 0

        total_paid = customer.payments.aggregate(
            total=Sum('amount_paid')
        )['total'] or 0

        outstanding_balance = total_udharo - total_paid

        if outstanding_balance <= 0:
            return Response(
                {"detail": "Customer has no outstanding balance."},
                status=status.HTTP_400_BAD_REQUEST
            )

        note = request.data.get('note', '')

        reminder = ReminderLog.objects.create(
            customer=customer,
            outstanding_balance=outstanding_balance,
            note=note
        )

        serializer = ReminderLogSerializer(reminder)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
