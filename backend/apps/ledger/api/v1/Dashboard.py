from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Sum
from django.utils import timezone
from django.core.cache import cache
from drf_spectacular.utils import extend_schema

from ...models import  UdharoEntry
from ...tasks.services import get_customers_with_balance

@extend_schema(tags=["Dashboard"])
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
