from django.urls import path

from .student_views import (
    StudentCourseDetailView,
    StudentCourseListView,
    StudentLessonDetailView,
)

app_name = "student-v1"

urlpatterns = [
    path("courses/", StudentCourseListView.as_view(), name="course-list"),
    path(
        "courses/<int:pk>/",
        StudentCourseDetailView.as_view(),
        name="course-detail",
    ),
    path(
        "lessons/<int:pk>/",
        StudentLessonDetailView.as_view(),
        name="lesson-detail",
    ),
]
