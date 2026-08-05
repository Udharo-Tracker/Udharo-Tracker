from django.contrib import admin
from .models import UdharoEntry, Payment, PaymentPhoto, Transaction, Allocation

# Register your models here.


@admin.register(UdharoEntry)
class UdharoEntryAdmin(admin.ModelAdmin):
    list_display = ["customer", "is_settled", "created_at", "settled_at"]


class PaymentPhotoInline(admin.TabularInline):
    model = PaymentPhoto
    extra = 0


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "customer",
        "amount_paid",
        "payment_mode",
        "reference",
        "transaction_date",
        "created_at",
    ]
    inlines = [PaymentPhotoInline]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "txn_number",
        "customer",
        "txn_type",
        "amount",
        "status",
        "transaction_date",
    ]


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = [
        "payment_transaction",
        "debt_transaction",
        "amount",
        "created_at",
    ]
