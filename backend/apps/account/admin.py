from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from apps.account.models import User
# from unfold.admin import ModelAdmin
# from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm


admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin):

    ordering = ["email"]

    list_display = (
        "id",
        "email",
        "username",
        "first_name",
        "last_name",
        "gender",
        "date_of_birth",
        "is_staff",
        "is_active",
    )

    list_filter = ("is_staff", "is_active")

    search_fields = ("email", "username", "first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "username",
                    "first_name",
                    "last_name",
                    "gender",
                    "date_of_birth",
                    "profile_picture",
                    "phone_number",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )