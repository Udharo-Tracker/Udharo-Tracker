from celery import shared_task


from apps.shops.models import Customer
from .services import calculate_credit_score


@shared_task
def recalculate_all_credit_scores():
    customers = Customer.objects.select_related("shop").iterator(chunk_size=1000)
    count = 0
    for customer in customers:
        calculate_credit_score(customer)
        count += 1
    return f"Recalculated scores for {count} customers"