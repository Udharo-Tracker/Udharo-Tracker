from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from ...models import User
from ...serializers.profile import UserProfileSerializers


class UserProfileViewSet(generics.RetrieveUpdateAPIView):
    queryset = User.objects.none()
    serializer_class = UserProfileSerializers
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
