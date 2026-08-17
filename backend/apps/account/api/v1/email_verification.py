from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from ...serializers.email_verification import (
    EmailVerifyConfirmSerializer,
    ResendVerificationEmailSerializer,
)


@extend_schema(tags=["Register"])
class EmailVerifyView(generics.GenericAPIView):
    serializer_class = EmailVerifyConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Email verified. You can now log in."})


@extend_schema(tags=["Register"])
class ResendVerificationEmailView(generics.GenericAPIView):
    serializer_class = ResendVerificationEmailSerializer
    permission_classes = [AllowAny]
    throttle_scope = "forgot_password"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                "message": "If that email is registered and unverified, a link has been sent."
            }
        )
