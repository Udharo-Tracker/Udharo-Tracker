from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from apps.shared.files_utils import FileSizeValidator, file_upload_path
from django.contrib.auth.base_user import BaseUserManager
import uuid

# Create your models here.
class User(AbstractUser):
    class GenderChoices(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'          
        OTHER = 'others', 'Others'
    
    class UserStatusChoices(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"
        
    username = models.CharField(
        _("username"),
        max_length=150,
        unique=True,
        blank=True,
        null=True,
        validators=[AbstractUser.username_validator],
        error_messages={
            "unique": _("A user with that username already exists."),
        },
    )

    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)

    password = models.CharField(max_length=128)
    is_phone_verified = models.BooleanField(default=False)

    # personal details
    first_name = models.CharField(_("first name"), max_length=150, blank=False)
    last_name = models.CharField(_("last name"), max_length=150, blank=False)
    gender = models.CharField(
        max_length=10, choices=GenderChoices.choices, blank=True, null=True
    )
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    profile_picture = models.ImageField(
        upload_to=file_upload_path,
        validators=[FileSizeValidator(1 * 1024 * 1024)],
        null=True,
        blank=True,
    )
    is_developer = models.BooleanField(default=False)
    status = models.CharField(
    max_length=20,
    choices=UserStatusChoices.choices,
    default=UserStatusChoices.ACTIVE,
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    class Meta:
        db_table = "users"


    def save(self, *args, **kwargs):
        if self.email:
            self.email = BaseUserManager().normalize_email(self.email)

        if not self.username:
            self.username = uuid.uuid4().hex[:30]

        super().save(*args, **kwargs)