from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...models import User
from ...serializers.password import (
    UserForgotPasswordSerializer,
    UserPasswordResetSerializer,
    UserUpdatePasswordSerializer,
)


class UserUpdatePasswordViewSet(generics.UpdateAPIView):
    queryset = User.objects.none()
    serializer_class = UserUpdatePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer(self, *args, **kwargs):
        kwargs["partial"] = False
        return super().get_serializer(*args, **kwargs)


class UserForgotPasswordViewSet(generics.GenericAPIView):
    serializer_class = UserForgotPasswordSerializer
    throttle_scope = "forgot_password"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Successfully sent password reset email."})


class UserPasswordResetViewSet(generics.UpdateAPIView):
    queryset = User.objects.none()
    serializer_class = UserPasswordResetSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Successfully reset password."})
