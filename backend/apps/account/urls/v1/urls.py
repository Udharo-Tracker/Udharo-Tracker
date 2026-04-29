from django.conf import settings
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenBlacklistView,
    TokenRefreshView,
    TokenVerifyView,
)

from apps.account.api.v1.authentication import CustomTokenObtainPairView 
from apps.account.api.v1.register import UserRegisterViewSet 
from apps.account.api.v1.password import UserForgotPasswordViewSet, UserPasswordResetViewSet, UserUpdatePasswordViewSet 
from apps.account.api.v1.profile import UserProfileViewSet

router = DefaultRouter()

# user
router.register(
    r"user/cregister",
    UserRegisterViewSet,
    basename="user-register",
)


urlpatterns = [
    path("", include(router.urls)),
    # auth
    path(
        "auth/ctoken/",
        CustomTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("auth/token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),


    # user
    path("user/profile/", UserProfileViewSet.as_view(), name="user-profile"),
    path(
        "user/change-password/",
        UserUpdatePasswordViewSet.as_view(),
        name="user-password",
    ),
    path(
        "user/cforgot-password/",
        UserForgotPasswordViewSet.as_view(),
        name="user-forgot-password",
    ),
    path(
        "user/password/reset/",
        UserPasswordResetViewSet.as_view(),
        name="user-password-reset",
    ),
    # path(
    #     "user/deactivate/",
    #     DeactivateAccountView.as_view(),
    #     name="user-deactivate",
    # ),
    # path("auth/", include("rest_social_auth.urls_jwt_pair")),
]
