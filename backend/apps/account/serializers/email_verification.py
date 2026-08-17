from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from ..mailers import send_verification_email
from ..models import User
from ..tokens import email_verification_token


class EmailVerifyConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(write_only=True)
    token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            uid = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid verification link.")

        if user.is_active:
            raise serializers.ValidationError("This account is already verified.")

        if not email_verification_token.check_token(user, attrs["token"]):
            raise serializers.ValidationError("Invalid or expired verification link.")

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.is_active = True
        user.save(update_fields=["is_active"])
        return user


class ResendVerificationEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        # Same "don't reveal whether this email is registered" shape as
        # UserForgotPasswordSerializer — resolved to a user (or None) here,
        # checked in save() rather than raised as a field error.
        try:
            return User.objects.get(email=value)
        except User.DoesNotExist:
            return None

    def save(self):
        user = self.validated_data["email"]
        if user is None or user.is_active:
            return
        send_verification_email(user)
