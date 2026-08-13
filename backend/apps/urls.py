from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.ledger.urls.v1.urls")),
    path("v1/", include("apps.shops.urls.v1.urls")),
    path("v1/", include("apps.account.urls.v1.urls")),
    path("v1/", include("apps.notifications.urls.v1.urls")),
]
