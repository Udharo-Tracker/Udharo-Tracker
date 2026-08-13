from rest_framework.routers import DefaultRouter
from django.urls import include, path

from apps.notifications.api.v1.notification import NotificationViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("", include(router.urls)),
]
