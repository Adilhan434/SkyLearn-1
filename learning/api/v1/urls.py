from django.urls import path

from .views import (
    CourseModuleDetailView,
    CourseTopicCreateView,
    CourseTopicDetailView,
)


app_name = "learning-v1"

urlpatterns = [
    path("modules/<int:pk>/", CourseModuleDetailView.as_view(), name="module-detail"),
    path(
        "modules/<int:module_pk>/topics/",
        CourseTopicCreateView.as_view(),
        name="topic-create",
    ),
    path("topics/<int:pk>/", CourseTopicDetailView.as_view(), name="topic-detail"),
]
