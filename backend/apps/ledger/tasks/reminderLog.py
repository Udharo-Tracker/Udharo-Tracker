from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Case, When, Value, CharField, Exists, OuterRef, Max, DecimalField, F, ExpressionWrapper, Q, Subquery
from django.db.models.functions import Coalesce


from apps.shops.models import Customer
from apps.ledger.models import UdharoEntry, ReminderLog, Payment


@shared_task
def send_daily_reminders():
    # your logic here
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)


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


    queryset = Customer.objects.filter(
            udharo_entries__is_settled = False,
            udharo_entries__created_at__lte=thirty_days_ago 
        ).annotate(
        total_udharo=Coalesce(
            Subquery(udharo_sum), 
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
        ).filter(outstanding_balance__gt=0).distinct()


    for customer in queryset:
        ReminderLog.objects.create(
            customer=customer,
            outstanding_balance=customer.outstanding_balance,
            note=f"Daily reminder for outstanding balance: Rs.{customer.outstanding_balance}",
            channel=ReminderLog.Channel.AUTO,
        )

    return f"Sent reminders to {queryset.count()} customers"