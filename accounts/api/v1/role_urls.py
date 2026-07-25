from django.urls import path

from .role_views import RoleListView


app_name = "roles"

urlpatterns = [
    path("", RoleListView.as_view(), name="list"),
]
