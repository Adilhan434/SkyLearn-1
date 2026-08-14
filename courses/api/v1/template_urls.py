from django.urls import path

from .template_views import (
    CourseTemplateCreateCourseView,
    CourseTemplateDetailView,
    CourseTemplateListCreateView,
)


app_name = "course-templates-v1"

urlpatterns = [
    path("", CourseTemplateListCreateView.as_view(), name="list-create"),
    path("<int:pk>/", CourseTemplateDetailView.as_view(), name="detail"),
    path(
        "<int:pk>/create-course/",
        CourseTemplateCreateCourseView.as_view(),
        name="create-course",
    ),
]
