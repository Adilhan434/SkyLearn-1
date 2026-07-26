from django.urls import path

from .user_views import UserDetailView, UserListCreateView


app_name = "users"

urlpatterns = [
    path("", UserListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", UserDetailView.as_view(), name="detail"),
]
