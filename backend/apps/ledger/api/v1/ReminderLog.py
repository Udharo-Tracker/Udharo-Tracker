from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from apps.shops.models import Customer
from ...models import ReminderLog
from ...serializers.ReminderLog import ReminderLogSerializer
from ...tasks.services import get_outstanding_balance
from ...services.sms import send_sms


class ReminderLogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(tags=["Reminder Log"], responses=ReminderLogSerializer(many=True))
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        logs = ReminderLog.objects.filter(customer=customer).order_by('-sent_at')
        serializer = ReminderLogSerializer(logs, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["Reminder Log"],
        request=OpenApiTypes.OBJECT,
        responses=ReminderLogSerializer,
        examples=[
            OpenApiExample(
                "Request example",
                value={"note": "Called customer, promised to pay by Friday"},
                request_only=True,
            ),
        ],
    )
    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        outstanding_balance = get_outstanding_balance(customer)

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


class ReminderSMSView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Reminder Log"],
        request=None,
        responses=ReminderLogSerializer,
        description="Sends an SMS reminder to the customer for their current outstanding balance.",
    )
    def post(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        if not customer.phone:
            return Response(
                {"detail": "Customer has no phone number on file."},
                status=status.HTTP_400_BAD_REQUEST
            )

        outstanding_balance = get_outstanding_balance(customer)

        if outstanding_balance <= 0:
            return Response(
                {"detail": "Customer has no outstanding balance."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message = (
            f"Dear {customer.name}, your outstanding balance at {customer.shop.name} "
            f"is Rs.{outstanding_balance}. Please clear it soon. Thank you."
        )

        result = send_sms(customer.phone, message)

        reminder = ReminderLog.objects.create(
            customer=customer,
            outstanding_balance=outstanding_balance,
            note=message,
            channel=ReminderLog.Channel.SMS,
            delivery_status="sent" if result["success"] else "failed",
        )

        serializer = ReminderLogSerializer(reminder)
        response_status = status.HTTP_201_CREATED if result["success"] else status.HTTP_502_BAD_GATEWAY
        return Response(serializer.data, status=response_status)
