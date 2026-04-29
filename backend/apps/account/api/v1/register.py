from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

from ...models import User
from ...serializers.register import UserRegisterSerializers


class UserRegisterViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.none()
    serializer_class = UserRegisterSerializers
    permission_classes = [AllowAny]
