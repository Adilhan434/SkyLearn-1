from django.urls import path

from .views import CourseModuleDetailView


app_name = "learning-v1"

urlpatterns = [
    path("modules/<int:pk>/", CourseModuleDetailView.as_view(), name="module-detail"),
]
