from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema

from ...serializers.authentication import CustomTokenObtainPairSerializer

@extend_schema(tags=["Register"])
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
