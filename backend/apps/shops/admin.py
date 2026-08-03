from django.contrib import admin
from .models import Shop, Customer


# Register your models here.


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'phone', 'created_at']

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop', 'phone', 'credit_limit', 'created_at']