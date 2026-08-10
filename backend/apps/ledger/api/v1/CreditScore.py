from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, OpenApiParameter


from apps.shops.models import Customer
from ...models import CreditScore
from ...filters import CreditScoreFilter
from ...serializers.CreditScore import CreditScoreSerializer


@extend_schema(
    tags=["Customers"],
    responses=CreditScoreSerializer,
)
class CustomerCreditScoreView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        latest = (
            CreditScore.objects.filter(customer=customer)
            .order_by("-calculated_at")
            .first()
        )

        if not latest:
            return Response({"message": "No score calculated yet"}, status=404)

        serializer = CreditScoreSerializer(latest)
        return Response(serializer.data)


@extend_schema(
    tags=["Customers"],
    responses=CreditScoreSerializer(many=True),
    parameters=[
        OpenApiParameter(
            name="risk_level",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Filter by risk level: green, yellow, or red.",
        ),
        OpenApiParameter(
            name="date_after",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only scores calculated on/after this date (YYYY-MM-DD).",
        ),
        OpenApiParameter(
            name="date_before",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Only scores calculated on/before this date (YYYY-MM-DD).",
        ),
    ],
)
class CustomerCreditScoreHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, id=customer_id)

        if customer.shop.owner != request.user:
            raise PermissionDenied()

        scores = CreditScore.objects.filter(customer=customer).order_by(
            "-calculated_at"
        )
        scores = CreditScoreFilter(request.query_params, queryset=scores).qs

        serializer = CreditScoreSerializer(scores, many=True)
        return Response(serializer.data)
