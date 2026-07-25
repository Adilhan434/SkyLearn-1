from django.urls import include, path

from .views import ApiV1RootView


app_name = "api-v1"

urlpatterns = [
    path("", ApiV1RootView.as_view(), name="root"),
    path("auth/", include("accounts.api.v1.auth_urls")),
    path("users/", include("accounts.api.v1.user_urls")),
    path("roles/", include("accounts.api.v1.role_urls")),
]
