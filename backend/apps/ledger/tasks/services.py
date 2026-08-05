from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
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


from ..models import Allocation, CreditScore, Transaction, TransactionCounter


def get_balance_breakdown(customer):
    """Single source of truth for {total_udharo, total_paid,
    outstanding_balance}. Reused by get_outstanding_balance and
    CustomerDetailSerializer so the aggregation logic lives in one place."""
    # Sum ALL entries (settled or not) so this stays in sync with total_paid,
    # which is also all-time. Filtering to is_settled=False here would make
    # paid-off entries vanish from the balance while their payments remain,
    # producing a false negative balance.
    total_udharo = (
        customer.udharo_entries.aggregate(total=Sum("items__amount"))["total"] or 0
    )

    total_paid = customer.payments.aggregate(total=Sum("amount_paid"))["total"] or 0

    outstanding_balance = customer.opening_balance + total_udharo - total_paid

    return {
        "total_udharo": total_udharo,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
    }


def get_outstanding_balance(customer):
    return get_balance_breakdown(customer)["outstanding_balance"]


def annotate_balance(queryset):
    """Annotate a Customer queryset with total_udharo/total_paid/
    outstanding_balance via Subquery, for list views that need the pooled
    balance without an N+1 per row. Factored out of get_customers_with_balance
    so CustomerViewSet.get_queryset can reuse it."""
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

    return queryset.annotate(
        total_udharo=Coalesce(
            Subquery(udharo_sum), Value(0), output_field=DecimalField()
        ),
        total_paid=Coalesce(
            Subquery(payment_sum), Value(0), output_field=DecimalField()
        ),
        outstanding_balance=ExpressionWrapper(
            F("opening_balance") + F("total_udharo") - F("total_paid"),
            output_field=DecimalField(),
        ),
    )


def get_allocated_amount(debt_transaction):
    """How much of a debt-type Transaction (opening/udharo) has been
    covered by Allocation rows so far."""
    return (
        debt_transaction.allocations_received.aggregate(total=Sum("amount"))["total"]
        or 0
    )


def _debt_transactions_with_unpaid(customer, only_unpaid=True):
    """Opening/udharo Transactions for a customer, annotated with
    allocated_amount/unpaid_amount, oldest first. Used both to pick FIFO
    targets for a new payment and to resync settlement status."""
    allocated_sum = (
        Allocation.objects.filter(debt_transaction=OuterRef("pk"))
        .values("debt_transaction")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    queryset = (
        Transaction.objects.filter(
            customer=customer,
            txn_type__in=[Transaction.TxnType.OPENING, Transaction.TxnType.UDHARO],
        )
        .annotate(
            allocated_amount=Coalesce(
                Subquery(allocated_sum), Value(0), output_field=DecimalField()
            ),
            unpaid_amount=ExpressionWrapper(
                F("amount") - F("allocated_amount"), output_field=DecimalField()
            ),
        )
        .order_by("transaction_date", "created_at")
    )

    if only_unpaid:
        queryset = queryset.filter(unpaid_amount__gt=0)

    return queryset


def allocate_payment_fifo(payment_transaction):
    """Greedily create Allocation rows for a payment-type Transaction with
    no existing allocations, against the customer's oldest unpaid debts
    first (opening, then udharo, ordered by transaction_date). Call inside
    the caller's own transaction.atomic() block."""
    remaining = payment_transaction.amount
    new_allocations = []

    for debt in _debt_transactions_with_unpaid(payment_transaction.customer):
        if remaining <= 0:
            break
        applied = min(remaining, debt.unpaid_amount)
        new_allocations.append(
            Allocation(
                payment_transaction=payment_transaction,
                debt_transaction=debt,
                amount=applied,
            )
        )
        remaining -= applied

    if new_allocations:
        Allocation.objects.bulk_create(new_allocations)


def reallocate_payment(payment_transaction):
    """Wipe this payment's existing allocations and re-FIFO-allocate its
    (possibly changed) amount from scratch. Scoped to this one payment —
    it does not reshuffle allocations already made by other payments."""
    Allocation.objects.filter(payment_transaction=payment_transaction).delete()
    allocate_payment_fifo(payment_transaction)


def build_balance_after_map(customer_id):
    """{transaction_id: running_balance} for one customer's full
    transaction history, walked oldest-first. Deliberately unpaginated so
    balance_after is correct regardless of which page a row falls on."""
    balance = 0
    balance_after_map = {}

    transactions = Transaction.objects.filter(customer_id=customer_id).order_by(
        "transaction_date", "created_at"
    )
    for txn in transactions:
        if txn.txn_type == Transaction.TxnType.PAYMENT:
            balance -= txn.amount
        else:
            balance += txn.amount
        balance_after_map[txn.id] = balance

    return balance_after_map


def build_running_totals_map(customer_id):
    """{transaction_id: (cumulative_debit, cumulative_credit)} for one
    customer's full transaction history, walked oldest-first — the two
    running ledger columns behind TransactionListSerializer's
    closing_balance_debit/closing_balance_credit. Unlike balance_after,
    these accumulate separately rather than netting against each other."""
    debit_total = 0
    credit_total = 0
    totals_map = {}

    transactions = Transaction.objects.filter(customer_id=customer_id).order_by(
        "transaction_date", "created_at"
    )
    for txn in transactions:
        if txn.txn_type == Transaction.TxnType.PAYMENT:
            credit_total += txn.amount
        else:
            debit_total += txn.amount
        totals_map[txn.id] = (debit_total, credit_total)

    return totals_map


def clear_ledger_cache(user):
    """Invalidate the per-user cached dashboard/ledger-summary responses.
    Call this after any write that can change a customer's balance."""
    cache.delete(f"ledger_summary_{user.id}")
    cache.delete(f"dashboard_{user.id}")


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

    outstanding = get_outstanding_balance(customer)

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


def sync_udharo_settlement(customer):
    """Recompute status ('open'/'closed') for every opening/udharo Transaction
    independently, based on its own allocations — not the pooled balance.
    One entry can now close while an older, still-unpaid one stays open;
    this must be re-run after anything that can move allocations: creating,
    editing, or deleting a Payment or UdharoEntry (or editing opening_balance).

    Call this from inside the caller's own transaction.atomic() block."""
    now = timezone.now()
    debts = list(_debt_transactions_with_unpaid(customer, only_unpaid=False))

    closed_ids = [d.id for d in debts if d.unpaid_amount <= 0]
    open_ids = [d.id for d in debts if d.unpaid_amount > 0]

    if closed_ids:
        Transaction.objects.filter(id__in=closed_ids).exclude(status="closed").update(
            status="closed"
        )
    if open_ids:
        Transaction.objects.filter(id__in=open_ids).exclude(status="open").update(
            status="open"
        )

    closed_entry_ids = [
        d.udharo_entry_id for d in debts if d.udharo_entry_id and d.unpaid_amount <= 0
    ]
    open_entry_ids = [
        d.udharo_entry_id for d in debts if d.udharo_entry_id and d.unpaid_amount > 0
    ]

    if closed_entry_ids:
        UdharoEntry.objects.filter(id__in=closed_entry_ids, is_settled=False).update(
            is_settled=True, settled_at=now
        )
    if open_entry_ids:
        UdharoEntry.objects.filter(id__in=open_entry_ids, is_settled=True).update(
            is_settled=False, settled_at=None
        )


def get_customers_with_balance(user):

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    fifteen_days_ago = now - timedelta(days=15)

    # 1. Build queryset with ALL annotations including risk
    queryset = (
        annotate_balance(Customer.objects.filter(shop__owner=user))
        .annotate(
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
