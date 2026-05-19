from django.utils import timezone
from datetime import timedelta
from django.db.models.functions import Coalesce
from django.db.models import Sum, Case, When, Value, CharField, Exists, OuterRef, Max, DecimalField, F, ExpressionWrapper, Q, Subquery

from apps.shops.models import Customer
from apps.ledger.models import UdharoEntry, Payment


from ..models import CreditScore


def calculate_credit_score(customer):
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    fifteen_days_ago = now - timedelta(days=15)
    score = 100

    # Check overdue entries
    has_thirty_days_overdue = customer.udharo_entries.filter(
        is_settled=False,
        created_at__lte=thirty_days_ago
    ).exists()

    has_fifteen_days_overdue = customer.udharo_entries.filter(
        is_settled=False,
        created_at__lte=fifteen_days_ago
    ).exists()


    # Calculate outstanding balance
    total_udharo = customer.udharo_entries.filter(
        is_settled=False
    ).aggregate(total=Sum('items__amount'))['total'] or 0

    total_paid = customer.payments.aggregate(
        total=Sum('amount_paid')
    )['total'] or 0

    outstanding = total_udharo - total_paid
    

    # Apply deductions
    late_payment_count = customer.payments.filter(
    created_at__gt=thirty_days_ago
    ).count()

    score -= late_payment_count * 10

    if has_thirty_days_overdue:
        score -= 40
    elif has_fifteen_days_overdue:
        score -= 20

    if outstanding > 0:
        score -= 10

    # Cap score first
    score = max(0, score)

    # Determine risk
    if score >= 70:
        risk = CreditScore.RiskChoices.GREEN
    elif score >= 40:
        risk = CreditScore.RiskChoices.YELLOW
    else:
        risk = CreditScore.RiskChoices.RED


    # Save snapshot    
    CreditScore.objects.create(
        customer=customer,
        score=score,
        risk_level=risk
    )

    return score


def get_customers_with_balance(user):

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    fifteen_days_ago = now - timedelta(days=15)

    udharo_sum = UdharoEntry.objects.filter(
        customer=OuterRef('pk'),
        is_settled=False
    ).values('customer').annotate(
        total=Sum('items__amount')
    ).values('total')

    payment_sum = Payment.objects.filter(
        customer=OuterRef('pk')
    ).values('customer').annotate(
        total=Sum('amount_paid')
    ).values('total')

    # 1. Build queryset with ALL annotations including risk
    queryset = Customer.objects.filter(
        shop__owner=user
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

    total_outstanding = queryset.aggregate(
    total=Sum('outstanding_balance')
    )['total'] or 0

    total_credit = queryset.aggregate(
    total=Sum('total_udharo')
    )['total'] or 0

    total_recovered = queryset.aggregate(
    total=Sum('total_paid')
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
    
    return {
        "customers": customers_summary,
        "total_credit": total_credit,
        "total_recovered": total_recovered,
        "total_outstanding": total_outstanding
    }
