import uuid
import re

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils.translation import gettext_lazy as _

from apps.shared.abstract_base_model import AbstractBaseModel
from apps.shared.files_utils import file_upload_path, FileSizeValidator, validate_phone




# =========================
# USER MANAGER (REQUIRED)
# =========================

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email).strip().lower()

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(email, password, **extra_fields)


# =========================
# USER MODEL
# =========================

class User(AbstractBaseUser, PermissionsMixin, AbstractBaseModel):

    class GenderChoices(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # core auth
    email = models.EmailField(_("email address"), unique=True)
    username = models.CharField(max_length=150, blank=True, null=True)

    # profile
    gender = models.CharField(
        max_length=10,
        choices=GenderChoices.choices,
        blank=True,
        null=True
    )

    date_of_birth = models.DateField(blank=True, null=True)

    profile_picture = models.ImageField(
        upload_to=file_upload_path,
        validators=[FileSizeValidator(1 * 1024 * 1024)],
        null=True,
        blank=True,
    )

    # 🇳🇵 Nepal phone number support
    phone_number = models.CharField(
        max_length=15,
        default="+9779000000000",
        validators=[validate_phone],
    )

    # auth flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # login field
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email

    # =========================
    # CLEAN SAVE LOGIC
    # =========================
    def save(self, *args, **kwargs):

        # email normalize
        if self.email:
            self.email = self.email.strip().lower()

        # auto username fallback (internal use only)
        if not self.username:
            self.username = str(uuid.uuid4())[:30]

        # 🇳🇵 Nepal phone normalization (+977)
        if self.phone_number:
            phone = re.sub(r"[\s\-]", "", self.phone_number)

            # already international format
            if phone.startswith("+"):
                self.phone_number = phone

            # Nepal local format handling
            elif phone.startswith("977"):
                self.phone_number = f"+{phone}"

            elif phone.startswith("0"):
                self.phone_number = f"+977{phone[1:]}"

            else:
                self.phone_number = f"+977{phone}"

        super().save(*args, **kwargs)