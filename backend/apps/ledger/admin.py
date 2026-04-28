from django.contrib import admin
from .models import UdharoEntry, Payment


# Register your models here.

@admin.register(UdharoEntry)
class UdharoEntryAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'is_settled', 'created_at', 'settled_at']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount_paid', 'created_at']