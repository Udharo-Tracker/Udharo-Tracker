from django.db import models
from apps.shops.models import Customer


# Create your models here.

class UdharoEntry(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='udharo_entries')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)
    is_settled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.amount}"


class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.name} - Rs.{self.amount_paid}"