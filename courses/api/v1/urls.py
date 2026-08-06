from django.urls import path

from .views import CourseDetailView, CourseListCreateView


app_name = "courses-v1"

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", CourseDetailView.as_view(), name="detail"),
]
