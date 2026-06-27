from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

# from ....mailers.password_reset_email import send_password_reset_email
from ..models import User


class UserUpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(
        validators=[validate_password],
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        user = self.context["request"].user
        old_password = attrs.get("old_password")
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if not all([old_password, password, confirm_password]):
            raise serializers.ValidationError(
                "old_password, password, and confirm_password are required."
            )

        if not user.check_password(old_password):
            raise serializers.ValidationError(
                {"old_password": "Old password is incorrect."}
            )

        if password != confirm_password:
            raise serializers.ValidationError(
                {"confirm_password": "Password fields didn't match."}
            )

        if password == old_password:
            raise serializers.ValidationError(
                {"password": "New password can't be the same as old password."}
            )

        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        return user


class UserForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            return User.objects.get(email=value)
        except User.DoesNotExist:
            return None

    def save(self):
        user = self.validated_data["email"]
        if user is None:
            return
        # send_password_reset_email(user, self.context.get("request"))


class UserPasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(
        validators=[validate_password],
        required=True,
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    token = serializers.CharField(write_only=True)
    uid = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid token.")

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid token.")

        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )

        validate_password(attrs["password"], user=user)

        attrs["user"] = user
        return attrs

    def save(self):
        password = self.validated_data["password"]
        user = self.validated_data["user"]
        user.set_password(password)
        user.save()
