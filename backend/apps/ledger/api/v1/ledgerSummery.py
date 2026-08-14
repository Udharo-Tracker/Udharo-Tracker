from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from ...tasks.services import get_customers_with_balance


@extend_schema(
    tags=["Ledger Summary"],
    responses=OpenApiResponse(
        response=OpenApiTypes.OBJECT,
        description="Total outstanding balance across all customers, with a per-customer breakdown and risk level.",
        examples=[
            OpenApiExample(
                "Example response",
                value={
                    "total_outstanding": 15200.0,
                    "customers_summary": [
                        {
                            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                            "name": "Ram Sharma",
                            "phone": "+9779812345678",
                            "created_at": "2026-07-01T09:00:00+05:45",
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
class LedgerSummaryView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):

        cache_key = f"ledger_summary_{request.user.id}"

        # 1. Check cache first
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        results = get_customers_with_balance(request.user)

        # Ledger summary lists customers newest-first by created_at,
        # unlike the dashboard which ranks them by outstanding balance.
        customers_summary = sorted(
            results["customers"],
            key=lambda customer: customer["created_at"] or "",
            reverse=True,
        )

        # 4. Cache and return
        content = {
            "total_outstanding": results["total_outstanding"],
            "customers_summary": customers_summary,
        }

        cache.set(cache_key, content, timeout=300)
        return Response(content)
