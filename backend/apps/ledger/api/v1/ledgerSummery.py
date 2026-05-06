from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models.functions import Coalesce
from django.db.models import Sum, Case, When, Value, CharField, Exists, OuterRef, Max, DecimalField, F, ExpressionWrapper, Q, Subquery
from django.utils import timezone
from datetime import timedelta
from rest_framework import permissions
from django.core.cache import cache

from apps.shops.models import Customer
from apps.ledger.models import UdharoEntry
from apps.ledger.models import Payment

class LedgerSummaryView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):

        cache_key = f"ledger_summary_{request.user.id}"
    
        # 1. Check cache first
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        fifteen_days_ago = now - timedelta(days=15)

        udharo_sum = UdharoEntry.objects.filter(
        customer=OuterRef('pk'),
        is_settled=False
        ).values('customer').annotate(
            total=Sum('amount')
        ).values('total')

        payment_sum = Payment.objects.filter(
            customer=OuterRef('pk')
        ).values('customer').annotate(
            total=Sum('amount_paid')
        ).values('total')


        # 1. Build queryset with ALL annotations including risk
        queryset = Customer.objects.filter(
            shop__owner=request.user
        ).annotate(
            total_udharo=Coalesce(
            Subquery(udharo_sum, filter=Q(udharo_entries__is_settled=False)), 
            Value(0), 
            output_field=DecimalField()
            ),
            total_paid=Coalesce(
            Subquery(payment_sum), 
            Value(0), 
            output_field=DecimalField()
            ),
            outstanding_balance=ExpressionWrapper(
            F('total_udharo') - F('total_paid'),
            output_field=DecimalField()
            ),
            last_udharo=Max('udharo_entries__created_at'),
            last_payment=Max('payments__created_at'),
            has_red=Exists(
            UdharoEntry.objects.filter(
                customer=OuterRef('pk'),
                is_settled=False,
                created_at__lte=thirty_days_ago
            )
            ),
            has_yellow=Exists(
            UdharoEntry.objects.filter(
                customer=OuterRef('pk'),
                is_settled=False,
                created_at__lte=fifteen_days_ago
            )
            ),
            risk=Case(
            When(has_red=True, then=Value('red')),
            When(has_yellow=True, then=Value('yellow')),
            default=Value('green'),
            output_field=CharField()
            )
        ).order_by('-outstanding_balance')

        # 2. Total outstanding at DB level
        total_outstanding = queryset.aggregate(
            total=Sum('outstanding_balance')
        )['total'] or 0

        # 3. Build response list
        customers_summary = []
        for item in queryset:
            last = max(filter(None, [item.last_udharo, item.last_payment])) \
                if any([item.last_udharo, item.last_payment]) else None
            
            customers_summary.append({
                "id": item.id,
                "name": item.name,
                "phone": item.phone,
                "total_udharo": item.total_udharo,
                "total_paid": item.total_paid,
                "outstanding_balance": item.outstanding_balance,
                "last_transaction": last.isoformat() if last else None,
                "risk": item.risk,
            })

        # 4. Cache and return
        content = {
            "total_outstanding": total_outstanding,
            "customers_summary": customers_summary
        }
        cache.set(cache_key, content, timeout=300)
        return Response(content)


