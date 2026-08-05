from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from django.db.models.functions import Coalesce
from django.db.models import (
    Sum,
    Case,
    When,
    Value,
    CharField,
    Exists,
    OuterRef,
    Max,
    DecimalField,
    F,
    ExpressionWrapper,
    Subquery,
)

from apps.shops.models import Customer
from apps.ledger.models import UdharoEntry, Payment


from ..models import CreditScore, Transaction, TransactionCounter


def get_outstanding_balance(customer):
    # Sum ALL entries (settled or not) so this stays in sync with total_paid,
    # which is also all-time. Filtering to is_settled=False here would make
    # paid-off entries vanish from the balance while their payments remain,
    # producing a false negative balance.
    total_udharo = (
        customer.udharo_entries.aggregate(total=Sum("items__amount"))["total"] or 0
    )

    total_paid = customer.payments.aggregate(total=Sum("amount_paid"))["total"] or 0

    return customer.opening_balance + total_udharo - total_paid


def calculate_credit_score(customer):
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    fifteen_days_ago = now - timedelta(days=15)
    score = 100

    # Check overdue entries
    has_thirty_days_overdue = customer.udharo_entries.filter(
        is_settled=False, created_at__lte=thirty_days_ago
    ).exists()

    has_fifteen_days_overdue = customer.udharo_entries.filter(
        is_settled=False, created_at__lte=fifteen_days_ago
    ).exists()

    # Calculate outstanding balance (all-time, same reasoning as get_outstanding_balance)
    total_udharo = (
        customer.udharo_entries.aggregate(total=Sum("items__amount"))["total"] or 0
    )

    total_paid = customer.payments.aggregate(total=Sum("amount_paid"))["total"] or 0

    outstanding = customer.opening_balance + total_udharo - total_paid

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
    CreditScore.objects.create(customer=customer, score=score, risk_level=risk)

    return score


def _next_txn_number(shop, txn_type):
    # select_for_update() locks the counter row for the duration of the
    # surrounding transaction.atomic() block so two concurrent requests for
    # the same shop+type can't read the same last_number and generate a
    # duplicate txn_number.
    with transaction.atomic():
        counter, _ = TransactionCounter.objects.select_for_update().get_or_create(
            shop=shop, txn_type=txn_type
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
    return f"{Transaction.TXN_PREFIX[txn_type]}-{counter.last_number}"


def record_transaction(
    *,
    customer,
    txn_type,
    amount,
    user,
    remarks="",
    status="",
    transaction_date=None,
    udharo_entry=None,
    payment=None,
):
    """Create a Transaction audit-trail row. Always call this from inside the
    caller's own transaction.atomic() block, so the counter increment and the
    Transaction row commit or roll back together with the source row."""
    return Transaction.objects.create(
        customer=customer,
        txn_type=txn_type,
        txn_number=_next_txn_number(customer.shop, txn_type),
        amount=amount,
        status=status,
        remarks=remarks,
        transaction_date=transaction_date or timezone.now(),
        recorded_by=user,
        udharo_entry=udharo_entry,
        payment=payment,
    )


def get_customers_with_balance(user):

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    fifteen_days_ago = now - timedelta(days=15)

    # All-time sum (settled or not) so it stays in sync with total_paid, which
    # is also all-time. Filtering to unsettled entries here would make paid-off
    # entries vanish from total_udharo while their payments remain in
    # total_paid, producing a false negative outstanding_balance.
    udharo_sum = (
        UdharoEntry.objects.filter(customer=OuterRef("pk"))
        .values("customer")
        .annotate(total=Sum("items__amount"))
        .values("total")
    )

    payment_sum = (
        Payment.objects.filter(customer=OuterRef("pk"))
        .values("customer")
        .annotate(total=Sum("amount_paid"))
        .values("total")
    )

    # 1. Build queryset with ALL annotations including risk
    queryset = (
        Customer.objects.filter(shop__owner=user)
        .annotate(
            total_udharo=Coalesce(
                Subquery(udharo_sum),
                Value(0),
                output_field=DecimalField(),
            ),
            total_paid=Coalesce(
                Subquery(payment_sum), Value(0), output_field=DecimalField()
            ),
            outstanding_balance=ExpressionWrapper(
                F("opening_balance") + F("total_udharo") - F("total_paid"),
                output_field=DecimalField(),
            ),
            last_udharo=Max("udharo_entries__created_at"),
            last_payment=Max("payments__created_at"),
            has_red=Exists(
                UdharoEntry.objects.filter(
                    customer=OuterRef("pk"),
                    is_settled=False,
                    created_at__lte=thirty_days_ago,
                )
            ),
            has_yellow=Exists(
                UdharoEntry.objects.filter(
                    customer=OuterRef("pk"),
                    is_settled=False,
                    created_at__lte=fifteen_days_ago,
                )
            ),
            risk=Case(
                When(has_red=True, then=Value("red")),
                When(has_yellow=True, then=Value("yellow")),
                default=Value("green"),
                output_field=CharField(),
            ),
        )
        .order_by("-outstanding_balance")
    )

    total_outstanding = (
        queryset.aggregate(total=Sum("outstanding_balance"))["total"] or 0
    )

    total_credit = queryset.aggregate(total=Sum("total_udharo"))["total"] or 0

    total_recovered = queryset.aggregate(total=Sum("total_paid"))["total"] or 0

    # 3. Build response list
    customers_summary = []
    for item in queryset:
        last = (
            max(filter(None, [item.last_udharo, item.last_payment]))
            if any([item.last_udharo, item.last_payment])
            else None
        )

        customers_summary.append(
            {
                "id": item.id,
                "name": item.name,
                "phone": item.phone,
                "total_udharo": item.total_udharo,
                "total_paid": item.total_paid,
                "outstanding_balance": item.outstanding_balance,
                "last_transaction": last.isoformat() if last else None,
                "risk": item.risk,
            }
        )

    return {
        "customers": customers_summary,
        "total_credit": total_credit,
        "total_recovered": total_recovered,
        "total_outstanding": total_outstanding,
    }
