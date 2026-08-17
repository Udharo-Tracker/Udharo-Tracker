from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from ..models import User
from ..mailers import send_verification_email
from django.db import transaction
from ...shops.models import Shop


class UserRegisterSerializers(serializers.ModelSerializer):
    password = serializers.CharField(
        validators=[validate_password],
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    # Shop fields
    shop_name = serializers.CharField(write_only=True)
    shop_phone = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )
    shop_address = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "gender",
            "date_of_birth",
            "profile_picture",
            "phone_number",
            "shop_name",
            "shop_phone",
            "shop_address",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords didn't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        # Extract shop fields properly
        shop_name = validated_data.pop("shop_name")
        shop_phone = validated_data.pop("shop_phone", "")
        shop_address = validated_data.pop("shop_address", "")

        with transaction.atomic():
            # Inactive until the verification link is clicked — SimpleJWT's
            # login already refuses inactive users, so this alone blocks
            # sign-in without any extra permission checks.
            user = User.objects.create_user(is_active=False, **validated_data)

            Shop.objects.create(
                owner=user,
                name=shop_name,
                phone=shop_phone,
                address=shop_address,
            )

            # Deferred to on_commit: only send the email if the whole
            # registration (user + shop) actually committed.
            transaction.on_commit(lambda: send_verification_email(user))

        return user
