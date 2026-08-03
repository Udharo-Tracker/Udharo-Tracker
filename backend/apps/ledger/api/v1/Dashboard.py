from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Sum
from django.utils import timezone
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from ...models import  UdharoEntry
from ...tasks.services import get_customers_with_balance

@extend_schema(
    tags=["Dashboard"],
    responses=OpenApiResponse(
        response=OpenApiTypes.OBJECT,
        description="Shop-wide dashboard totals plus the top 5 customers by outstanding balance.",
        examples=[
            OpenApiExample(
                "Example response",
                value={
                    "total_credit_given": 42000.0,
                    "total_recovered": 26800.0,
                    "total_pending": 15200.0,
                    "todays_udharo": 1500.0,
                    "top_5_debtors": [
                        {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "name": "Ram Sharma",
                            "phone": "+9779812345678",
                            "total_udharo": 5000.0,
                            "total_paid": 2000.0,
                            "outstanding_balance": 3000.0,
                            "last_transaction": "2026-07-15T10:30:00+05:45",
                            "risk": "yellow",
                        }
                    ],
                },
                response_only=True,
            ),
        ],
    ),
)
class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):

        cache_key = f"dashboard_{request.user.id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        today = timezone.now().date()
        results = get_customers_with_balance(request.user)

        todays_udharo = UdharoEntry.objects.filter(
            customer__shop__owner=request.user,
            created_at__date=today
        ).aggregate(total=Sum('items__amount'))['total'] or 0

        content = {
            "total_credit_given": results["total_credit"],
            "total_recovered": results["total_recovered"],
            "total_pending": results["total_outstanding"],
            "todays_udharo": todays_udharo,
            "top_5_debtors": results["customers"][:5]
            }
        
        cache.set(cache_key, content, timeout=300)
        return Response(content)
