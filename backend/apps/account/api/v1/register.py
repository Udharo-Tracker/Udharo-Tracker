from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema

from ...models import User
from ...serializers.register import UserRegisterSerializers

@extend_schema(tags=["Register"])
class UserRegisterViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.none()
    serializer_class = UserRegisterSerializers
    permission_classes = [AllowAny]
