from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.core.cache import cache
from drf_spectacular.utils import extend_schema

from ...tasks.services import get_customers_with_balance

@extend_schema(
    tags=["Ledger Summary"],
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

        # 4. Cache and return
        content = {
            "total_outstanding": results["total_outstanding"],
            "customers_summary": results["customers"]
        }

        cache.set(cache_key, content, timeout=300)
        return Response(content)


