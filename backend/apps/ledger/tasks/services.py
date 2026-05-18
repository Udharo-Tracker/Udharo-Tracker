from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum


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

