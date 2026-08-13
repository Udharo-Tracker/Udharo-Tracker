import uuid
from django.db import models
from django.conf import settings

from apps.shared.files_utils import file_upload_path, FileSizeValidator


# Create your models here.
class Shop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shop"
    )
    name = models.CharField(max_length=255)
    # Registered/legal business name, if different from the shop's display name.
    legal_name = models.CharField(max_length=255, blank=True)
    # Nepal PAN/VAT number.
    tax_number = models.CharField(max_length=20, blank=True)
    logo = models.ImageField(
        upload_to=file_upload_path,
        validators=[FileSizeValidator(1 * 1024 * 1024)],
        null=True,
        blank=True,
    )
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_term_days = models.PositiveIntegerField(default=0)
    loyalty_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    opening_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"
